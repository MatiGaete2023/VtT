package cl.vtt.transcriptor

/**
 * Mantiene cargado el modelo de whisper.cpp y realiza la transcripcion.
 * Reutiliza el modelo entre transcripciones (como en la version de PC).
 *
 * `loadModel`/`transcribe`/`free` son `@Synchronized` sobre el mismo monitor:
 * whisper_full (nativeTranscribe) puede tardar bastante y correr en un hilo
 * de fondo que sobrevive a la rotacion de pantalla (ver TranscribeViewModel).
 * Sin este candado, `free()` podria liberar el contexto nativo mientras otro
 * hilo todavia esta transcribiendo con el, causando un crash nativo
 * (use-after-free). El candado garantiza que `free()` espera a que cualquier
 * transcripcion en curso termine antes de liberar memoria.
 *
 * `requestAbort()` es la excepcion deliberada: NO es `@Synchronized`, porque
 * si lo fuera, cancelar tendria que esperar a que `transcribe()` termine (el
 * mismo trabajo que se quiere cortar). Lee `ctxPtr` (marcado `@Volatile` para
 * verlo actualizado entre hilos sin bloquear) y llama al nativo directamente;
 * ver el comentario en whisper_jni.cpp sobre por que eso es seguro incluso
 * frente a `free()` corriendo en paralelo.
 */
class Transcriber {

    private val bridge = WhisperBridge()
    @Volatile private var ctxPtr = 0L
    private var loadedModel: String? = null

    @Synchronized
    fun loadModel(modelPath: String, modelName: String) {
        if (loadedModel == modelName && ctxPtr != 0L) return
        freeInternal()
        ctxPtr = bridge.nativeInit(modelPath)
        check(ctxPtr != 0L) { "No se pudo cargar el modelo '$modelName'" }
        loadedModel = modelName
    }

    /**
     * lang: "es", "en", ... o null/"" para deteccion automatica.
     * onProgress: se invoca desde este mismo hilo (el que llama a transcribe)
     * con el avance 0..100, si whisper.cpp lo reporta.
     */
    @Synchronized
    fun transcribe(audio: FloatArray, lang: String?, onProgress: ((Int) -> Unit)? = null): String {
        check(ctxPtr != 0L) { "El modelo no esta cargado" }
        val threads = Runtime.getRuntime().availableProcessors().coerceIn(2, 8)
        val listener = onProgress?.let { cb -> WhisperBridge.ProgressListener { pct -> cb(pct) } }
        return bridge.nativeTranscribe(ctxPtr, audio, lang, threads, listener).trim()
    }

    /** Pide cancelar la transcripcion en curso (si hay una). Ver nota de clase. */
    fun requestAbort() {
        val ptr = ctxPtr
        if (ptr != 0L) bridge.nativeRequestAbort(ptr)
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
