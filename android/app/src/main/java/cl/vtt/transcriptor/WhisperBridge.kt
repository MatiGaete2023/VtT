package cl.vtt.transcriptor

/**
 * Puente con la libreria nativa whisper.cpp (libwhisper_jni.so).
 * Toda la transcripcion ocurre en el dispositivo, sin conexion.
 */
class WhisperBridge {

    /** Llamado desde el hilo nativo mientras transcribe, con el avance 0..100. */
    fun interface ProgressListener {
        fun onProgress(pct: Int)
    }

    external fun nativeInit(modelPath: String): Long

    external fun nativeFree(handle: Long)

    /** Pide cancelar una transcripcion en curso con este handle (cualquier hilo). */
    external fun nativeRequestAbort(handle: Long)

    /** Prepara un handle ya cargado para un nuevo trabajo, antes de decodificar. */
    external fun nativeResetAbort(handle: Long)

    external fun nativeTranscribe(
        handle: Long,
        audio: FloatArray,
        lang: String?,
        nThreads: Int,
        listener: ProgressListener?
    ): String

    companion object {
        init {
            System.loadLibrary("whisper_jni")
        }
    }
}
