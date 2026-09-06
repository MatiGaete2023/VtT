package cl.vtt.transcriptor

import android.content.Context
import org.json.JSONObject
import java.io.File

/**
 * Persistencia mínima del último documento. Se guarda en almacenamiento
 * interno de la app para que una terminación del proceso no borre una
 * transcripción que el usuario todavía no había exportado.
 *
 * El audio original no se copia aquí: el documento conserva solo metadatos,
 * texto reconocido y texto revisado. El respaldo automático de la app está
 * desactivado en el manifest porque el contenido puede ser sensible.
 */
data class SavedTranscription(
    val original: String,
    val edited: String?,
    val sourceName: String?,
    val model: String,
    val language: String,
    val updatedAt: Long,
    val segments: List<TranscriptionSegment>
)

object TranscriptionStore {
    private const val FILE_NAME = "ultimo_documento.json"

    private fun file(context: Context): File =
        File(File(context.filesDir, "proyectos").apply { mkdirs() }, FILE_NAME)

    @Synchronized
    fun save(
        context: Context,
        original: String,
        edited: String?,
        sourceName: String?,
        model: String,
        language: String,
        segments: List<TranscriptionSegment> = emptyList()
    ) {
        val segmentosJson = org.json.JSONArray()
        segments.forEach { segmento ->
            segmentosJson.put(
                JSONObject()
                    .put("startMs", segmento.startMs)
                    .put("endMs", segmento.endMs)
                    .put("text", segmento.text)
            )
        }
        val json = JSONObject()
            .put("original", original)
            .put("edited", edited)
            .put("sourceName", sourceName)
            .put("model", model)
            .put("language", language)
            .put("segments", segmentosJson)
            .put("updatedAt", System.currentTimeMillis())
        val target = file(context)
        val partial = File(target.parentFile, "$FILE_NAME.part")
        partial.writeText(json.toString(), Charsets.UTF_8)
        if (!partial.renameTo(target)) {
            partial.copyTo(target, overwrite = true)
            partial.delete()
        }
    }

    fun load(context: Context): SavedTranscription? {
        val target = file(context)
        if (!target.isFile) return null
        return try {
            val json = JSONObject(target.readText(Charsets.UTF_8))
            val segmentosJson = json.optJSONArray("segments")
            val segmentos = buildList {
                if (segmentosJson != null) {
                    for (i in 0 until segmentosJson.length()) {
                        val item = segmentosJson.optJSONObject(i) ?: continue
                        add(
                            TranscriptionSegment(
                                item.optLong("startMs"),
                                item.optLong("endMs"),
                                item.optString("text")
                            )
                        )
                    }
                }
            }
            SavedTranscription(
                original = json.optString("original", ""),
                edited = if (json.isNull("edited")) null else json.optString("edited"),
                sourceName = if (json.isNull("sourceName")) null else json.optString("sourceName"),
                model = json.optString("model", "base"),
                language = json.optString("language", ""),
                updatedAt = json.optLong("updatedAt", 0L),
                segments = segmentos
            ).takeIf { it.original.isNotEmpty() }
        } catch (_: Exception) {
            null
        }
    }
}
