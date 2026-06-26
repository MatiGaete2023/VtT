package cl.vtt.transcriptor

/**
 * Puente con la libreria nativa whisper.cpp (libwhisper_jni.so).
 * Toda la transcripcion ocurre en el dispositivo, sin conexion.
 */
class WhisperBridge {

    external fun nativeInit(modelPath: String): Long

    external fun nativeFree(ptr: Long)

    external fun nativeTranscribe(
        ptr: Long,
        audio: FloatArray,
        lang: String?,
        nThreads: Int
    ): String

    companion object {
        init {
            System.loadLibrary("whisper_jni")
        }
    }
}
