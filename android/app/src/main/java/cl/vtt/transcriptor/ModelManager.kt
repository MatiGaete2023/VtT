package cl.vtt.transcriptor

import android.content.Context
import java.io.File
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest

/**
 * Gestiona la descarga y almacenamiento de modelos GGML de whisper.cpp.
 *
 * Desde septiembre de 2026 tiny/base/small se validan contra SHA-256 esperados
 * publicados por el repositorio oficial ggerganov/whisper.cpp en Hugging Face.
 * Los sidecars locales se mantienen para cachear/verificar integridad, pero ya
 * no constituyen la unica confianza de la primera descarga.
 */
object ModelManager {

    private val hashesVerificados = mutableMapOf<String, Pair<Long, Long>>()

    private const val BASE_URL =
        "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/"

    val MODELS = listOf("tiny", "base", "small")

    /** SHA-256 de los blobs GGML multilingües que descarga esta app. */
    private val EXPECTED_SHA256 = mapOf(
        "tiny" to "be07e048e1e599ad46341c8d2a135645097a538221678b7acdd1b1919c6e1b21",
        "base" to "60ed5bc3dd14eea856493d334349b405782ddcaf0028d4b5df4088345fba2efe",
        "small" to "1be3a9b2063867b937e64e2ec7483364a79917e157fa98c5d94b5c1fffea987b"
    )

    fun modelFile(context: Context, model: String): File {
        require(model in MODELS) { "Modelo no soportado: $model" }
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
        if (model !in MODELS) return false
        val f = modelFile(context, model)
        if (!f.exists()) return false
        val sf = sizeFile(context, model)
        val esperadoTamano = sf.takeIf { it.exists() }?.readText()?.trim()?.toLongOrNull()
        if (esperadoTamano != null && f.length() != esperadoTamano) return false
        if (esperadoTamano == null && f.length() <= 1_000_000L) return false

        val sourceHash = EXPECTED_SHA256[model]
            ?: return false // MODELS y catálogo deben mantenerse sincronizados.
        val firma = f.length() to f.lastModified()
        val ruta = f.absolutePath
        synchronized(hashesVerificados) {
            if (hashesVerificados[ruta] == firma) return true
        }

        val actual = try { sha256(f) } catch (_: Exception) { return false }
        if (actual != sourceHash) return false

        // Repara/migra sidecars antiguos solo después de autenticar contra el
        // hash esperado de origen.
        if (esperadoTamano == null) sf.writeText(f.length().toString())
        val hf = hashFile(context, model)
        if (!hf.exists() || hf.readText().trim().lowercase() != sourceHash) {
            hf.writeText(sourceHash)
        }
        synchronized(hashesVerificados) { hashesVerificados[ruta] = firma }
        return true
    }

    fun ensureModel(
        context: Context,
        model: String,
        isCancelled: () -> Boolean = { false },
        onProgress: (Int) -> Unit
    ): File {
        require(model in MODELS) { "Modelo no soportado: $model" }
        val target = modelFile(context, model)
        if (isDownloaded(context, model)) return target

        if (target.exists()) target.delete()
        hashFile(context, model).delete()
        sizeFile(context, model).delete()

        val tmp = partFile(context, model)
        val url = URL(BASE_URL + "ggml-$model.bin")
        var existentes = if (tmp.exists()) tmp.length() else 0L

        var conn = abrirConexion(url, existentes)
        var totalEsperado = -1L
        try {
            conn.connect()
            var reanudando = existentes > 0L
            if (reanudando && conn.responseCode != HttpURLConnection.HTTP_PARTIAL) {
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
            tmp.delete()
            throw IOException(
                "Descarga incompleta: se recibieron $tamanoFinal de $totalEsperado bytes"
            )
        }
        val hashFinal = sha256(tmp)
        val hashEsperado = EXPECTED_SHA256.getValue(model)
        if (hashFinal != hashEsperado) {
            tmp.delete()
            throw IOException(
                "SHA-256 inválido para '$model'. La descarga no coincide con el modelo oficial esperado."
            )
        }
        if (!tmp.renameTo(target)) {
            tmp.copyTo(target, overwrite = true)
            tmp.delete()
        }
        sizeFile(context, model).writeText(tamanoFinal.toString())
        hashFile(context, model).writeText(hashEsperado)
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
