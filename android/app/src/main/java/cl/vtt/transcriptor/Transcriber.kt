package cl.vtt.transcriptor

/**
 * Mantiene cargado el modelo de whisper.cpp y realiza la transcripcion.
 * Reutiliza el modelo entre transcripciones (como en la version de PC).
 */
class Transcriber {

    private val bridge = WhisperBridge()
    private var ctxPtr = 0L
    private var loadedModel: String? = null

    fun loadModel(modelPath: String, modelName: String) {
        if (loadedModel == modelName && ctxPtr != 0L) return
        free()
        ctxPtr = bridge.nativeInit(modelPath)
        check(ctxPtr != 0L) { "No se pudo cargar el modelo '$modelName'" }
        loadedModel = modelName
    }

    /** lang: "es", "en", ... o null/"" para deteccion automatica. */
    fun transcribe(audio: FloatArray, lang: String?): String {
        check(ctxPtr != 0L) { "El modelo no esta cargado" }
        val threads = Runtime.getRuntime().availableProcessors().coerceIn(2, 8)
        return bridge.nativeTranscribe(ctxPtr, audio, lang, threads).trim()
    }

    fun free() {
        if (ctxPtr != 0L) {
            bridge.nativeFree(ctxPtr)
            ctxPtr = 0L
            loadedModel = null
        }
    }
}
