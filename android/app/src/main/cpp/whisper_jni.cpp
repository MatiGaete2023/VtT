// Puente JNI entre la app Android (Kotlin) y whisper.cpp.
// Expone: inicializar el modelo, transcribir un buffer de audio PCM (con
// progreso y cancelacion), y liberar.
#include <jni.h>
#include <atomic>
#include <cctype>
#include <cstdio>
#include <string>
#include <vector>
#include <android/log.h>

#include "whisper.h"

#define LOG_TAG "WhisperJNI"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, LOG_TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)

namespace {

// El "handle" que se entrega a Kotlin envuelve el contexto de whisper.cpp
// junto con una bandera de cancelacion. whisper_full() sondea esta bandera
// via abort_callback (tipo ggml_abort_callback: bool(*)(void*)) durante el
// computo, asi que puede cancelarse en cualquier momento desde otro hilo
// simplemente escribiendo en el atomic (sin volver a llamar a la JVM).
struct Handle {
    struct whisper_context *ctx;
    std::atomic<bool> abort{false};
};

bool abort_trampoline(void *data) {
    return reinterpret_cast<std::atomic<bool> *>(data)->load();
}

// Contexto para reenviar el progreso a un listener de Kotlin durante la
// misma llamada (mismo hilo, mismo JNIEnv que entro a nativeTranscribe).
struct ProgressCtx {
    JNIEnv *env;
    jobject listener;   // instancia de WhisperBridge.ProgressListener
    jmethodID method;   // onProgress(I)V
};

std::string escapar_json(const char *texto) {
    std::string salida;
    if (texto == nullptr) return salida;
    for (const unsigned char *p = reinterpret_cast<const unsigned char *>(texto); *p; ++p) {
        switch (*p) {
            case '\\': salida += "\\\\"; break;
            case '"':  salida += "\\\""; break;
            case '\n': salida += "\\n"; break;
            case '\r': salida += "\\r"; break;
            case '\t': salida += "\\t"; break;
            default:
                if (*p < 0x20) {
                    char buffer[7];
                    snprintf(buffer, sizeof(buffer), "\\u%04x", *p);
                    salida += buffer;
                } else {
                    salida += static_cast<char>(*p);
                }
        }
    }
    return salida;
}

void progress_trampoline(struct whisper_context * /*ctx*/, struct whisper_state * /*state*/,
                          int progress, void *userData) {
    auto *pc = reinterpret_cast<ProgressCtx *>(userData);
    if (pc != nullptr && pc->listener != nullptr) {
        pc->env->CallVoidMethod(pc->listener, pc->method, static_cast<jint>(progress));
    }
}

} // namespace

extern "C" {

// Inicializa el contexto de whisper a partir de un archivo de modelo .bin (ggml).
// Devuelve un handle (como long) o 0 si falla.
JNIEXPORT jlong JNICALL
Java_cl_vtt_transcriptor_WhisperBridge_nativeInit(
        JNIEnv *env, jobject /* this */, jstring jModelPath) {
    const char *modelPath = env->GetStringUTFChars(jModelPath, nullptr);
    LOGI("Cargando modelo: %s", modelPath);

    struct whisper_context_params cparams = whisper_context_default_params();
    cparams.use_gpu = false;

    struct whisper_context *ctx =
            whisper_init_from_file_with_params(modelPath, cparams);

    env->ReleaseStringUTFChars(jModelPath, modelPath);

    if (ctx == nullptr) {
        LOGE("No se pudo cargar el modelo");
        return 0;
    }
    auto *handle = new Handle{ctx};
    return reinterpret_cast<jlong>(handle);
}

// Libera el contexto de whisper (pesado: cientos de MB del modelo).
//
// A proposito NO se hace `delete handle`: nativeRequestAbort() puede recibir
// este mismo puntero desde otro hilo sin sincronizarse con esta llamada (ver
// comentario en Transcriber.kt), justo cuando se libera. Mantener el Handle
// (unos pocos bytes) vivo para siempre evita un use-after-free a cambio de
// una fuga minima y acotada: ocurre como mucho una vez por ciclo de vida del
// ViewModel, no por cada transcripcion.
JNIEXPORT void JNICALL
Java_cl_vtt_transcriptor_WhisperBridge_nativeFree(
        JNIEnv * /* env */, jobject /* this */, jlong handlePtr) {
    if (handlePtr != 0) {
        auto *handle = reinterpret_cast<Handle *>(handlePtr);
        whisper_free(handle->ctx);
        handle->ctx = nullptr;
    }
}

// Pide que una transcripcion en curso (con este handle) se detenga lo antes
// posible. Seguro de llamar desde cualquier hilo (bandera atomica).
JNIEXPORT void JNICALL
Java_cl_vtt_transcriptor_WhisperBridge_nativeRequestAbort(
        JNIEnv * /* env */, jobject /* this */, jlong handlePtr) {
    if (handlePtr != 0) {
        reinterpret_cast<Handle *>(handlePtr)->abort.store(true);
    }
}

JNIEXPORT void JNICALL
Java_cl_vtt_transcriptor_WhisperBridge_nativeResetAbort(
        JNIEnv * /* env */, jobject /* this */, jlong handlePtr) {
    if (handlePtr != 0) {
        reinterpret_cast<Handle *>(handlePtr)->abort.store(false);
    }
}

// Transcribe audio mono a 16 kHz (float [-1,1]).
// lang: codigo ISO ("es", "en", ...) o cadena vacia/null para deteccion automatica.
// listener: objeto con metodo onProgress(int), o null si no interesa el progreso.
// Devuelve un JSON con texto y segmentos temporales; usa prefijos reservados
// para distinguir error nativo y cancelacion de una transcripcion sin voz.
JNIEXPORT jstring JNICALL
Java_cl_vtt_transcriptor_WhisperBridge_nativeTranscribe(
        JNIEnv *env, jobject /* this */, jlong handlePtr,
        jfloatArray jAudio, jstring jLang, jint nThreads, jobject jListener) {

    if (handlePtr == 0) {
        return env->NewStringUTF("__VTT_ERROR__:contexto nativo invalido");
    }
    auto *handle = reinterpret_cast<Handle *>(handlePtr);
    if (handle->ctx == nullptr) {
        return env->NewStringUTF("__VTT_ERROR__:modelo no cargado");
    }
    if (handle->abort.load()) {
        return env->NewStringUTF("__VTT_CANCELLED__");
    }

    const jsize n = env->GetArrayLength(jAudio);
    std::vector<float> audio(static_cast<size_t>(n));
    env->GetFloatArrayRegion(jAudio, 0, n, audio.data());

    const char *lang = nullptr;
    if (jLang != nullptr) {
        lang = env->GetStringUTFChars(jLang, nullptr);
    }

    whisper_full_params wparams =
            whisper_full_default_params(WHISPER_SAMPLING_GREEDY);
    wparams.print_realtime   = false;
    wparams.print_progress   = false;
    wparams.print_timestamps = false;
    wparams.print_special    = false;
    wparams.translate        = false;
    wparams.single_segment   = false;
    wparams.no_context       = true;
    wparams.n_threads        = nThreads > 0 ? nThreads : 4;
    wparams.token_timestamps = true;

    if (lang != nullptr && lang[0] != '\0') {
        wparams.language = lang;        // idioma forzado
    } else {
        wparams.language = nullptr;     // deteccion automatica
    }

    wparams.abort_callback = abort_trampoline;
    wparams.abort_callback_user_data = &handle->abort;

    ProgressCtx progressCtx{env, nullptr, nullptr};
    if (jListener != nullptr) {
        jclass listenerClass = env->GetObjectClass(jListener);
        jmethodID mid = env->GetMethodID(listenerClass, "onProgress", "(I)V");
        if (mid != nullptr) {
            progressCtx.listener = jListener;
            progressCtx.method = mid;
            wparams.progress_callback = progress_trampoline;
            wparams.progress_callback_user_data = &progressCtx;
        } else {
            env->ExceptionClear();  // GetMethodID deja una excepcion pendiente si no encontro el metodo
        }
    }

    std::string result;
    const int rc = whisper_full(handle->ctx, wparams, audio.data(), static_cast<int>(audio.size()));
    if (rc == 0 && !handle->abort.load()) {
        const int nSeg = whisper_full_n_segments(handle->ctx);
        result = "{\"text\":\"";
        std::string textoCompleto;
        for (int i = 0; i < nSeg; ++i) {
            const char *segText = whisper_full_get_segment_text(handle->ctx, i);
            if (segText != nullptr) {
                textoCompleto += segText;
            }
        }
        result += escapar_json(textoCompleto.c_str());
        result += "\",\"segments\":[";
        for (int i = 0; i < nSeg; ++i) {
            if (i > 0) result += ",";
            const char *segText = whisper_full_get_segment_text(handle->ctx, i);
            const int64_t t0 = whisper_full_get_segment_t0(handle->ctx, i);
            const int64_t t1 = whisper_full_get_segment_t1(handle->ctx, i);
            result += "{\"startMs\":" + std::to_string(t0 * 10) +
                      ",\"endMs\":" + std::to_string(t1 * 10) +
                      ",\"text\":\"" + escapar_json(segText) + "\",\"words\":[";
            std::string palabra;
            int64_t inicio_palabra = -1;
            int64_t fin_palabra = -1;
            bool primera_palabra = true;
            const auto emitir_palabra = [&]() {
                if (palabra.empty()) return;
                if (!primera_palabra) result += ",";
                primera_palabra = false;
                result += "{\"startMs\":" +
                          (inicio_palabra >= 0 ? std::to_string(inicio_palabra * 10) : "null") +
                          ",\"endMs\":" +
                          (fin_palabra >= 0 ? std::to_string(fin_palabra * 10) : "null") +
                          ",\"text\":\"" + escapar_json(palabra.c_str()) + "\"}";
                palabra.clear();
                inicio_palabra = -1;
                fin_palabra = -1;
            };
            const int nTokens = whisper_full_n_tokens(handle->ctx, i);
            for (int j = 0; j < nTokens; ++j) {
                const char *token_text = whisper_full_get_token_text(handle->ctx, i, j);
                if (token_text == nullptr || token_text[0] == '\0') continue;
                const auto token = whisper_full_get_token_data(handle->ctx, i, j);
                const bool separa = !palabra.empty() &&
                    std::isspace(static_cast<unsigned char>(token_text[0]));
                if (separa) emitir_palabra();
                while (*token_text &&
                       std::isspace(static_cast<unsigned char>(*token_text))) ++token_text;
                if (token_text[0] == '\0') continue;
                if (inicio_palabra < 0) inicio_palabra = token.t0;
                fin_palabra = token.t1;
                palabra += token_text;
            }
            emitir_palabra();
            result += "]}";
        }
        result += "]}";
    } else if (rc != 0) {
        LOGE("whisper_full fallo con codigo %d", rc);
        result = "__VTT_ERROR__:el motor nativo fallo (codigo " + std::to_string(rc) + ")";
    } else {
        LOGI("Transcripcion cancelada por el usuario");
        result = "__VTT_CANCELLED__";
    }

    if (lang != nullptr) {
        env->ReleaseStringUTFChars(jLang, lang);
    }

    return env->NewStringUTF(result.c_str());
}

} // extern "C"
