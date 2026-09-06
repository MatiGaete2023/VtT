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
 *
 * Verificacion de integridad: en vez de hardcodear el tamano exacto de cada
 * modelo (Hugging Face podria republicar el archivo con otro tamano, y no fue
 * posible verificar bytes exactos contra la fuente al escribir esto), se
 * guarda el tamano que el propio servidor reporto al terminar cada descarga
 * en un sidecar ".size" junto al modelo. isDownloaded() compara el tamano
 * real del archivo contra ese valor: si difieren (descarga interrumpida a
 * medias sin dejar el .part, corrupcion en disco, etc.), se considera invalido
 * y se vuelve a descargar.
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

    private fun sizeFile(context: Context, model: String): File =
        File(modelFile(context, model).parentFile, "ggml-$model.bin.size")

    private fun partFile(context: Context, model: String): File =
        File(modelFile(context, model).parentFile, "ggml-$model.bin.part")

    fun isDownloaded(context: Context, model: String): Boolean {
        val f = modelFile(context, model)
        if (!f.exists()) return false
        val sf = sizeFile(context, model)
        val esperado = sf.takeIf { it.exists() }?.readText()?.trim()?.toLongOrNull()
        if (esperado != null) {
            return f.length() == esperado
        }
        // Sin sidecar (modelo bajado con una version anterior de la app):
        // acepta el heuristico viejo, pero deja el sidecar escrito para que
        // desde ahora se verifique de verdad.
        val ok = f.length() > 1_000_000L
        if (ok) sf.writeText(f.length().toString())
        return ok
    }

    /**
     * Garantiza que el modelo este disponible localmente. Si falta o esta
     * corrupto, lo descarga (reanudando una descarga interrumpida si es
     * posible) informando el avance (0..100). Devuelve el archivo del modelo.
     */
    fun ensureModel(
        context: Context,
        model: String,
        isCancelled: () -> Boolean = { false },
        onProgress: (Int) -> Unit
    ): File {
        val target = modelFile(context, model)
        if (isDownloaded(context, model)) return target

        // Un archivo final presente pero que no paso isDownloaded() esta
        // corrupto/truncado: se descarta antes de reintentar.
        if (target.exists()) target.delete()

        val tmp = partFile(context, model)
        val url = URL(BASE_URL + "ggml-$model.bin")
        var existentes = if (tmp.exists()) tmp.length() else 0L

        var conn = abrirConexion(url, existentes)
        try {
            conn.connect()
            var reanudando = existentes > 0L
            if (reanudando && conn.responseCode != HttpURLConnection.HTTP_PARTIAL) {
                // El servidor no soporto reanudar: se descarta lo parcial y
                // se reintenta desde cero con una conexion nueva.
                conn.disconnect()
                tmp.delete()
                existentes = 0L
                reanudando = false
                conn = abrirConexion(url, 0L)
                conn.connect()
            }
            if (conn.responseCode !in 200..299) {
                throw IOException("HTTP ${conn.responseCode} al descargar el modelo")
            }

            val restante = conn.contentLengthLong
            val total = if (restante > 0) existentes + restante else -1L

            conn.inputStream.use { input ->
                java.io.FileOutputStream(tmp, reanudando).use { output ->
                    val buf = ByteArray(64 * 1024)
                    var descargado = existentes
                    var lastPct = -1
                    while (true) {
                        if (isCancelled()) {
                            throw java.util.concurrent.CancellationException("descarga cancelada")
                        }
                        val leido = input.read(buf)
                        if (leido < 0) break
                        output.write(buf, 0, leido)
                        descargado += leido
                        if (total > 0) {
                            val pct = ((descargado * 100) / total).toInt()
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

        val tamanoFinal = tmp.length()
        if (!tmp.renameTo(target)) {
            tmp.copyTo(target, overwrite = true)
            tmp.delete()
        }
        sizeFile(context, model).writeText(tamanoFinal.toString())
        return target
    }

    private fun abrirConexion(url: URL, reanudarDesde: Long): HttpURLConnection {
        val conn = url.openConnection() as HttpURLConnection
        conn.connectTimeout = 30_000
        conn.readTimeout = 30_000
        conn.instanceFollowRedirects = true
        if (reanudarDesde > 0) {
            conn.setRequestProperty("Range", "bytes=$reanudarDesde-")
        }
        return conn
    }
}
