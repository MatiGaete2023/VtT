package cl.vtt.transcriptor

/**
 * Mantiene cargado el modelo de whisper.cpp y realiza la transcripcion.
 * Reutiliza el modelo entre transcripciones (como en la version de PC).
 *
 * Todos los metodos son `@Synchronized` sobre el mismo monitor: whisper_full
 * (nativeTranscribe) puede tardar bastante y correr en un hilo de fondo que
 * sobrevive a la rotacion de pantalla (ver TranscribeViewModel). Sin este
 * candado, `free()` podria liberar el contexto nativo mientras otro hilo
 * todavia esta transcribiendo con el, causando un crash nativo (use-after-free).
 * El candado garantiza que `free()` espera a que cualquier transcripcion en
 * curso termine antes de liberar memoria.
 */
class Transcriber {

    private val bridge = WhisperBridge()
    private var ctxPtr = 0L
    private var loadedModel: String? = null

    @Synchronized
    fun loadModel(modelPath: String, modelName: String) {
        if (loadedModel == modelName && ctxPtr != 0L) return
        freeInternal()
        ctxPtr = bridge.nativeInit(modelPath)
        check(ctxPtr != 0L) { "No se pudo cargar el modelo '$modelName'" }
        loadedModel = modelName
    }

    /** lang: "es", "en", ... o null/"" para deteccion automatica. */
    @Synchronized
    fun transcribe(audio: FloatArray, lang: String?): String {
        check(ctxPtr != 0L) { "El modelo no esta cargado" }
        val threads = Runtime.getRuntime().availableProcessors().coerceIn(2, 8)
        return bridge.nativeTranscribe(ctxPtr, audio, lang, threads).trim()
    }

    @Synchronized
    fun free() = freeInternal()

    private fun freeInternal() {
        if (ctxPtr != 0L) {
            bridge.nativeFree(ctxPtr)
            ctxPtr = 0L
            loadedModel = null
        }
    }
}
