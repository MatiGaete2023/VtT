package cl.vtt.transcriptor

import android.content.Context
import java.io.File
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest

/**
 * Gestiona la descarga (una sola vez) y el almacenamiento de los modelos GGML
 * de whisper.cpp. Una vez descargado, el modelo queda en el equipo y se usa
 * sin conexion.
 *
 * Verificacion de integridad local: se guardan el tamano y SHA-256 del archivo
 * terminado en sidecars junto al modelo. Esto detecta truncamiento o corrupcion
 * posterior en el almacenamiento. No sustituye un hash esperado publicado por
 * una fuente confiable para autenticar la primera descarga.
 */
object ModelManager {

    private val hashesVerificados = mutableMapOf<String, Pair<Long, Long>>()

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

    private fun hashFile(context: Context, model: String): File =
        File(modelFile(context, model).parentFile, "ggml-$model.bin.sha256")

    private fun partFile(context: Context, model: String): File =
        File(modelFile(context, model).parentFile, "ggml-$model.bin.part")

    fun isDownloaded(context: Context, model: String): Boolean {
        val f = modelFile(context, model)
        if (!f.exists()) return false
        val sf = sizeFile(context, model)
        val esperado = sf.takeIf { it.exists() }?.readText()?.trim()?.toLongOrNull()
        if (esperado != null && f.length() != esperado) return false
        if (esperado == null && f.length() <= 1_000_000L) return false

        val hf = hashFile(context, model)
        val hashEsperado = hf.takeIf { it.exists() }?.readText()?.trim()?.lowercase()
        val firma = f.length() to f.lastModified()
        if (hashEsperado != null) {
            val ruta = f.absolutePath
            synchronized(hashesVerificados) {
                if (hashesVerificados[ruta] == firma) return true
            }
            val hashActual = try { sha256(f) } catch (_: Exception) { return false }
            if (hashEsperado != hashActual) return false
            synchronized(hashesVerificados) { hashesVerificados[ruta] = firma }
            return true
        }

        val hashActual = try { sha256(f) } catch (_: Exception) { return false }

        // Migra modelos antiguos: desde ahora quedan protegidos también
        // contra corrupción silenciosa posterior a la descarga.
        if (esperado == null) sf.writeText(f.length().toString())
        hf.writeText(hashActual)
        synchronized(hashesVerificados) { hashesVerificados[f.absolutePath] = firma }
        return true
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
        var totalEsperado = -1L
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

            if (reanudando) {
                val inicio = inicioContentRange(conn.getHeaderField("Content-Range"))
                if (inicio != existentes) {
                    // Nunca anexar bytes si el servidor respondió un rango
                    // distinto del solicitado: se reinicia de forma segura.
                    conn.disconnect()
                    tmp.delete()
                    existentes = 0L
                    reanudando = false
                    conn = abrirConexion(url, 0L)
                    conn.connect()
                    if (conn.responseCode !in 200..299) {
                        throw IOException("HTTP ${conn.responseCode} al reiniciar la descarga")
                    }
                }
            }

            val restante = conn.contentLengthLong
            totalEsperado = if (conn.responseCode == HttpURLConnection.HTTP_PARTIAL) {
                totalContentRange(conn.getHeaderField("Content-Range"))
            } else if (restante > 0) {
                restante
            } else {
                -1L
            }

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
                        if (totalEsperado > 0) {
                            val pct = ((descargado * 100) / totalEsperado).toInt()
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
        if (totalEsperado > 0 && tamanoFinal != totalEsperado) {
            throw IOException(
                "Descarga incompleta: se recibieron $tamanoFinal de $totalEsperado bytes"
            )
        }
        val hashFinal = sha256(tmp)
        if (!tmp.renameTo(target)) {
            tmp.copyTo(target, overwrite = true)
            tmp.delete()
        }
        sizeFile(context, model).writeText(tamanoFinal.toString())
        hashFile(context, model).writeText(hashFinal)
        synchronized(hashesVerificados) {
            hashesVerificados[target.absolutePath] = target.length() to target.lastModified()
        }
        return target
    }

    private fun inicioContentRange(value: String?): Long? =
        value?.substringAfter("bytes ", "")
            ?.substringBefore('-')
            ?.toLongOrNull()

    private fun totalContentRange(value: String?): Long =
        value?.substringAfter('/', "")?.toLongOrNull() ?: -1L

    private fun sha256(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { input ->
            val buffer = ByteArray(64 * 1024)
            while (true) {
                val read = input.read(buffer)
                if (read < 0) break
                digest.update(buffer, 0, read)
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it.toInt() and 0xff) }
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
