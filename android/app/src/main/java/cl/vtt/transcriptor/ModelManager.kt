package cl.vtt.transcriptor

import android.content.Context
import java.io.File
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL

/**
 * Gestiona la descarga (una sola vez) y el almacenamiento de los modelos GGML
 * de whisper.cpp. Una vez descargado, el modelo queda en el equipo y se usa
 * sin conexion.
 */
object ModelManager {

    // Modelos multilingue oficiales de whisper.cpp publicados en Hugging Face.
    private const val BASE_URL =
        "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/"

    // Etiqueta visible -> nombre del modelo. tiny es el mas liviano (~75 MB),
    // small el mas preciso de la lista (~466 MB).
    val MODELS = listOf("tiny", "base", "small")

    fun modelFile(context: Context, model: String): File {
        val dir = File(context.filesDir, "models").apply { mkdirs() }
        return File(dir, "ggml-$model.bin")
    }

    fun isDownloaded(context: Context, model: String): Boolean {
        val f = modelFile(context, model)
        return f.exists() && f.length() > 1_000_000L
    }

    /**
     * Garantiza que el modelo este disponible localmente. Si falta, lo descarga
     * informando el avance (0..100). Devuelve el archivo del modelo.
     */
    fun ensureModel(context: Context, model: String, onProgress: (Int) -> Unit): File {
        val target = modelFile(context, model)
        if (isDownloaded(context, model)) return target

        val tmp = File(target.parentFile, "${target.name}.part")
        if (tmp.exists()) tmp.delete()

        val conn = (URL("$BASE_URL" + "ggml-$model.bin").openConnection() as HttpURLConnection).apply {
            connectTimeout = 30_000
            readTimeout = 30_000
            instanceFollowRedirects = true
        }

        try {
            conn.connect()
            if (conn.responseCode !in 200..299) {
                throw IOException("HTTP ${conn.responseCode} al descargar el modelo")
            }
            val total = conn.contentLengthLong
            conn.inputStream.use { input ->
                tmp.outputStream().use { output ->
                    val buf = ByteArray(64 * 1024)
                    var downloaded = 0L
                    var lastPct = -1
                    while (true) {
                        val read = input.read(buf)
                        if (read < 0) break
                        output.write(buf, 0, read)
                        downloaded += read
                        if (total > 0) {
                            val pct = ((downloaded * 100) / total).toInt()
                            if (pct != lastPct) {
                                lastPct = pct
                                onProgress(pct)
                            }
                        }
                    }
                }
            }
        } finally {
            conn.disconnect()
        }

        if (!tmp.renameTo(target)) {
            tmp.copyTo(target, overwrite = true)
            tmp.delete()
        }
        return target
    }
}
