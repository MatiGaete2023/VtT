package cl.vtt.transcriptor

import org.json.JSONObject

data class TranscriptionSegment(
    val startMs: Long,
    val endMs: Long,
    val text: String,
    /** Tiempos estimados por el motor; lista vacía si no estuvieron disponibles. */
    val words: List<TranscriptionWord> = emptyList()
)

data class TranscriptionWord(
    val startMs: Long?,
    val endMs: Long?,
    val text: String
)

data class TranscriptionResult(
    val text: String,
    val segments: List<TranscriptionSegment>
)

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
    fun transcribe(
        audio: FloatArray,
        lang: String?,
        onProgress: ((Int) -> Unit)? = null
    ): TranscriptionResult {
        check(ctxPtr != 0L) { "El modelo no esta cargado" }
        val threads = Runtime.getRuntime().availableProcessors().coerceIn(2, 8)
        val listener = onProgress?.let { cb -> WhisperBridge.ProgressListener { pct -> cb(pct) } }
        val raw = bridge.nativeTranscribe(ctxPtr, audio, lang, threads, listener).trim()
        return when {
            raw == "__VTT_CANCELLED__" ->
                throw java.util.concurrent.CancellationException("cancelada")
            raw.startsWith("__VTT_ERROR__:") ->
                throw IllegalStateException(raw.removePrefix("__VTT_ERROR__:").ifBlank {
                    "Error del motor nativo"
                })
            else -> {
                val json = JSONObject(raw)
                val segmentosJson = json.optJSONArray("segments")
                val segmentos = buildList {
                    if (segmentosJson != null) {
                        for (i in 0 until segmentosJson.length()) {
                            val item = segmentosJson.optJSONObject(i) ?: continue
                            val palabrasJson = item.optJSONArray("words")
                            val palabras = buildList {
                                if (palabrasJson != null) {
                                    for (j in 0 until palabrasJson.length()) {
                                        val palabra = palabrasJson.optJSONObject(j) ?: continue
                                        add(TranscriptionWord(
                                            if (palabra.isNull("startMs")) null else palabra.optLong("startMs"),
                                            if (palabra.isNull("endMs")) null else palabra.optLong("endMs"),
                                            palabra.optString("text")
                                        ))
                                    }
                                }
                            }
                            add(
                                TranscriptionSegment(
                                    item.optLong("startMs"),
                                    item.optLong("endMs"),
                                    item.optString("text"),
                                    palabras
                                )
                            )
                        }
                    }
                }
                TranscriptionResult(json.optString("text"), segmentos)
            }
        }
    }

    /** Pide cancelar la transcripcion en curso (si hay una). Ver nota de clase. */
    fun requestAbort() {
        val ptr = ctxPtr
        if (ptr != 0L) bridge.nativeRequestAbort(ptr)
    }

    fun resetAbort() {
        val ptr = ctxPtr
        if (ptr != 0L) bridge.nativeResetAbort(ptr)
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
