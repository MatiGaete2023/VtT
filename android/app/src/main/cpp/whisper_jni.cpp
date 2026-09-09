// Puente JNI entre la app Android y whisper.cpp.
#include <jni.h>
#include <atomic>
#include <cctype>
#include <cstdio>
#include <memory>
#include <mutex>
#include <string>
#include <unordered_map>
#include <vector>
#include <android/log.h>

#include "whisper.h"

#define LOG_TAG "WhisperJNI"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, LOG_TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)

namespace {

// El jlong expuesto a Kotlin ya no es un puntero crudo sino un id opaco. El
// registro entrega shared_ptr temporales: nativeFree puede retirar el id sin
// dejar un puntero colgante si requestAbort entra simultaneamente. ctx_mutex
// protege la vida del contexto pesado; abort sigue siendo atomico y no toma
// ese mutex para poder cancelar whisper_full mientras esta ejecutandose.
struct Handle {
    struct whisper_context *ctx;
    std::atomic<bool> abort{false};
    std::mutex ctx_mutex;

    explicit Handle(struct whisper_context *value) : ctx(value) {}
    ~Handle() {
        if (ctx != nullptr) {
            whisper_free(ctx);
            ctx = nullptr;
        }
    }
};

std::mutex g_handles_mutex;
std::unordered_map<jlong, std::shared_ptr<Handle>> g_handles;
std::atomic<jlong> g_next_handle_id{1};

jlong register_handle(const std::shared_ptr<Handle> &handle) {
    jlong id = g_next_handle_id.fetch_add(1);
    if (id <= 0) {
        // El overflow es practicamente inalcanzable; aun asi evita el 0
        // reservado y vuelve a una secuencia positiva.
        g_next_handle_id.store(2);
        id = 1;
    }
    std::lock_guard<std::mutex> lock(g_handles_mutex);
    g_handles[id] = handle;
    return id;
}

std::shared_ptr<Handle> get_handle(jlong id) {
    if (id == 0) return nullptr;
    std::lock_guard<std::mutex> lock(g_handles_mutex);
    auto it = g_handles.find(id);
    return it == g_handles.end() ? nullptr : it->second;
}

std::shared_ptr<Handle> remove_handle(jlong id) {
    if (id == 0) return nullptr;
    std::lock_guard<std::mutex> lock(g_handles_mutex);
    auto it = g_handles.find(id);
    if (it == g_handles.end()) return nullptr;
    auto value = it->second;
    g_handles.erase(it);
    return value;
}

bool abort_trampoline(void *data) {
    return reinterpret_cast<std::atomic<bool> *>(data)->load();
}

struct ProgressCtx {
    JNIEnv *env;
    jobject listener;
    jmethodID method;
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

JNIEXPORT jlong JNICALL
Java_cl_vtt_transcriptor_WhisperBridge_nativeInit(
        JNIEnv *env, jobject /* this */, jstring jModelPath) {
    const char *modelPath = env->GetStringUTFChars(jModelPath, nullptr);
    LOGI("Cargando modelo: %s", modelPath);

    struct whisper_context_params cparams = whisper_context_default_params();
    cparams.use_gpu = false;
    struct whisper_context *ctx = whisper_init_from_file_with_params(modelPath, cparams);
    env->ReleaseStringUTFChars(jModelPath, modelPath);

    if (ctx == nullptr) {
        LOGE("No se pudo cargar el modelo");
        return 0;
    }
    return register_handle(std::make_shared<Handle>(ctx));
}

JNIEXPORT void JNICALL
Java_cl_vtt_transcriptor_WhisperBridge_nativeFree(
        JNIEnv * /* env */, jobject /* this */, jlong handleId) {
    auto handle = remove_handle(handleId);
    if (!handle) return;
    handle->abort.store(true);
    std::lock_guard<std::mutex> lock(handle->ctx_mutex);
    if (handle->ctx != nullptr) {
        whisper_free(handle->ctx);
        handle->ctx = nullptr;
    }
    // shared_ptr libera tambien el Handle cuando termina cualquier
    // requestAbort concurrente. No queda la fuga deliberada anterior.
}

JNIEXPORT void JNICALL
Java_cl_vtt_transcriptor_WhisperBridge_nativeRequestAbort(
        JNIEnv * /* env */, jobject /* this */, jlong handleId) {
    auto handle = get_handle(handleId);
    if (handle) handle->abort.store(true);
}

JNIEXPORT void JNICALL
Java_cl_vtt_transcriptor_WhisperBridge_nativeResetAbort(
        JNIEnv * /* env */, jobject /* this */, jlong handleId) {
    auto handle = get_handle(handleId);
    if (handle) handle->abort.store(false);
}

JNIEXPORT jstring JNICALL
Java_cl_vtt_transcriptor_WhisperBridge_nativeTranscribe(
        JNIEnv *env, jobject /* this */, jlong handleId,
        jfloatArray jAudio, jstring jLang, jint nThreads, jobject jListener) {

    auto handle = get_handle(handleId);
    if (!handle) {
        return env->NewStringUTF("__VTT_ERROR__:contexto nativo invalido");
    }
    // nativeFree espera este mutex; requestAbort no lo necesita.
    std::unique_lock<std::mutex> ctxLock(handle->ctx_mutex);
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

    whisper_full_params wparams = whisper_full_default_params(WHISPER_SAMPLING_GREEDY);
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
        wparams.language = lang;
    } else {
        wparams.language = nullptr;
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
            env->ExceptionClear();
        }
    }

    std::string result;
    const int rc = whisper_full(
        handle->ctx, wparams, audio.data(), static_cast<int>(audio.size())
    );
    if (rc == 0 && !handle->abort.load()) {
        const int nSeg = whisper_full_n_segments(handle->ctx);
        result = "{\"text\":\"";
        std::string textoCompleto;
        for (int i = 0; i < nSeg; ++i) {
            const char *segText = whisper_full_get_segment_text(handle->ctx, i);
            if (segText != nullptr) textoCompleto += segText;
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
                while (*token_text && std::isspace(static_cast<unsigned char>(*token_text))) {
                    ++token_text;
                }
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
