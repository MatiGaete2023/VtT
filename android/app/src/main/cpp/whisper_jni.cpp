// Puente JNI entre la app Android (Kotlin) y whisper.cpp.
// Expone: inicializar el modelo, transcribir un buffer de audio PCM y liberar.
#include <jni.h>
#include <string>
#include <vector>
#include <android/log.h>

#include "whisper.h"

#define LOG_TAG "WhisperJNI"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, LOG_TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)

extern "C" {

// Inicializa el contexto de whisper a partir de un archivo de modelo .bin (ggml).
// Devuelve un puntero (como long) o 0 si falla.
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
    return reinterpret_cast<jlong>(ctx);
}

// Libera el contexto de whisper.
JNIEXPORT void JNICALL
Java_cl_vtt_transcriptor_WhisperBridge_nativeFree(
        JNIEnv * /* env */, jobject /* this */, jlong ptr) {
    if (ptr != 0) {
        whisper_free(reinterpret_cast<struct whisper_context *>(ptr));
    }
}

// Transcribe audio mono a 16 kHz (float [-1,1]).
// lang: codigo ISO ("es", "en", ...) o cadena vacia/null para deteccion automatica.
// Devuelve el texto transcrito (segmentos separados por salto de linea).
JNIEXPORT jstring JNICALL
Java_cl_vtt_transcriptor_WhisperBridge_nativeTranscribe(
        JNIEnv *env, jobject /* this */, jlong ptr,
        jfloatArray jAudio, jstring jLang, jint nThreads) {

    auto *ctx = reinterpret_cast<struct whisper_context *>(ptr);
    if (ctx == nullptr) {
        return env->NewStringUTF("");
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

    if (lang != nullptr && lang[0] != '\0') {
        wparams.language = lang;        // idioma forzado
    } else {
        wparams.language = nullptr;     // deteccion automatica
    }

    std::string result;
    const int rc = whisper_full(ctx, wparams, audio.data(), static_cast<int>(audio.size()));
    if (rc == 0) {
        const int nSeg = whisper_full_n_segments(ctx);
        for (int i = 0; i < nSeg; ++i) {
            const char *segText = whisper_full_get_segment_text(ctx, i);
            if (segText != nullptr) {
                result += segText;
            }
        }
    } else {
        LOGE("whisper_full fallo con codigo %d", rc);
    }

    if (lang != nullptr) {
        env->ReleaseStringUTFChars(jLang, lang);
    }

    return env->NewStringUTF(result.c_str());
}

} // extern "C"
