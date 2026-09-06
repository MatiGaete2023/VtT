package cl.vtt.transcriptor

import android.content.Context
import android.media.MediaCodec
import android.media.MediaExtractor
import android.media.MediaFormat
import android.media.MediaMetadataRetriever
import android.net.Uri
import java.io.ByteArrayOutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder

/**
 * Decodifica cualquier audio/video soportado por Android (mp3, m4a, aac, ogg,
 * wav, mp4, etc.) a PCM float mono normalizado [-1, 1] a 16 kHz, que es lo que
 * espera whisper.cpp.
 *
 * Nota: `decode()` mantiene todo el audio en memoria como FloatArray (4 bytes
 * por muestra, ~230 MB por hora a 16 kHz). Para audios muy largos (varias
 * horas) esto puede agotar la memoria del proceso; el llamador debe capturar
 * OutOfMemoryError (ver TranscribeViewModel) y sugerir un archivo más corto.
 */
object AudioDecoder {

    const val TARGET_RATE = 16_000

    private class Pcm(val bytes: ByteArray, val sampleRate: Int, val channels: Int)

    /** Duracion aproximada en segundos via metadata (barato, no decodifica el
     * archivo). Devuelve null si no se pudo determinar. */
    fun duracionSegundos(context: Context, uri: Uri): Long? {
        val retriever = MediaMetadataRetriever()
        return try {
            retriever.setDataSource(context, uri)
            retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION)
                ?.toLongOrNull()?.let { it / 1000 }
        } catch (_: Exception) {
            null
        } finally {
            try {
                retriever.release()
            } catch (_: Exception) { /* nada mas que hacer */ }
        }
    }

    fun decode(context: Context, uri: Uri): FloatArray {
        val extractor = MediaExtractor()
        val pfd = context.contentResolver.openFileDescriptor(uri, "r")
            ?: throw IllegalArgumentException("No se pudo abrir el archivo de audio")

        return try {
            pfd.use {
                extractor.setDataSource(it.fileDescriptor)
                val trackIndex = selectAudioTrack(extractor)
                require(trackIndex >= 0) { "El archivo no contiene una pista de audio" }
                extractor.selectTrack(trackIndex)

                val format = extractor.getTrackFormat(trackIndex)
                val mime = format.getString(MediaFormat.KEY_MIME)
                    ?: throw IllegalArgumentException("Formato de audio desconocido")
                val srcRate = format.getInteger(MediaFormat.KEY_SAMPLE_RATE)
                val srcChannels = format.getInteger(MediaFormat.KEY_CHANNEL_COUNT)

                val pcm = decodePcm16(extractor, format, mime, srcRate, srcChannels)
                val shorts = ShortArray(pcm.bytes.size / 2)
                ByteBuffer.wrap(pcm.bytes).order(ByteOrder.LITTLE_ENDIAN)
                    .asShortBuffer().get(shorts)

                val mono = downmixToMono(shorts, pcm.channels)
                resample(mono, pcm.sampleRate, TARGET_RATE)
            }
        } finally {
            try {
                extractor.release()
            } catch (_: Exception) {
                // El extractor puede haberse liberado por el proveedor.
            }
        }
    }

    private fun selectAudioTrack(extractor: MediaExtractor): Int {
        for (i in 0 until extractor.trackCount) {
            val mime = extractor.getTrackFormat(i).getString(MediaFormat.KEY_MIME) ?: continue
            if (mime.startsWith("audio/")) return i
        }
        return -1
    }

    private fun decodePcm16(
        extractor: MediaExtractor,
        inputFormat: MediaFormat,
        mime: String,
        fallbackRate: Int,
        fallbackChannels: Int
    ): Pcm {
        val codec = MediaCodec.createDecoderByType(mime)
        try {
            codec.configure(inputFormat, null, null, 0)
            codec.start()

            val bos = ByteArrayOutputStream()
            val info = MediaCodec.BufferInfo()
            val timeoutUs = 10_000L
            var sawInputEOS = false
            var sawOutputEOS = false
            var outRate = fallbackRate
            var outChannels = fallbackChannels

            while (!sawOutputEOS) {
            if (!sawInputEOS) {
                val inIndex = codec.dequeueInputBuffer(timeoutUs)
                if (inIndex >= 0) {
                    val inputBuffer = codec.getInputBuffer(inIndex)!!
                    val sampleSize = extractor.readSampleData(inputBuffer, 0)
                    if (sampleSize < 0) {
                        codec.queueInputBuffer(
                            inIndex, 0, 0, 0, MediaCodec.BUFFER_FLAG_END_OF_STREAM
                        )
                        sawInputEOS = true
                    } else {
                        codec.queueInputBuffer(inIndex, 0, sampleSize, extractor.sampleTime, 0)
                        extractor.advance()
                    }
                }
            }

            val outIndex = codec.dequeueOutputBuffer(info, timeoutUs)
            when {
                outIndex >= 0 -> {
                    if (info.size > 0) {
                        val outputBuffer = codec.getOutputBuffer(outIndex)
                        if (outputBuffer != null) {
                            outputBuffer.position(info.offset)
                            outputBuffer.limit(info.offset + info.size)
                            val chunk = ByteArray(info.size)
                            outputBuffer.get(chunk)
                            bos.write(chunk)
                        }
                    }
                    codec.releaseOutputBuffer(outIndex, false)
                    if (info.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM != 0) {
                        sawOutputEOS = true
                    }
                }
                outIndex == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED -> {
                    val of = codec.outputFormat
                    if (of.containsKey(MediaFormat.KEY_SAMPLE_RATE)) {
                        outRate = of.getInteger(MediaFormat.KEY_SAMPLE_RATE)
                    }
                    if (of.containsKey(MediaFormat.KEY_CHANNEL_COUNT)) {
                        outChannels = of.getInteger(MediaFormat.KEY_CHANNEL_COUNT)
                    }
                }
            }
            }
            return Pcm(bos.toByteArray(), outRate, outChannels)
        } finally {
            try {
                codec.stop()
            } catch (_: Exception) {
                // Puede fallar si configure/start no llegó a completarse.
            }
            try {
                codec.release()
            } catch (_: Exception) {
                // Liberación idempotente para proveedores defectuosos.
            }
        }
    }

    private fun downmixToMono(pcm: ShortArray, channels: Int): FloatArray {
        if (channels <= 1) {
            val mono = FloatArray(pcm.size)
            for (i in pcm.indices) mono[i] = pcm[i] / 32768f
            return mono
        }
        val frames = pcm.size / channels
        val mono = FloatArray(frames)
        var idx = 0
        for (f in 0 until frames) {
            var acc = 0f
            for (c in 0 until channels) acc += pcm[idx++] / 32768f
            mono[f] = acc / channels
        }
        return mono
    }

    private fun resample(input: FloatArray, srcRate: Int, dstRate: Int): FloatArray {
        if (srcRate == dstRate || input.isEmpty()) return input
        val ratio = dstRate.toDouble() / srcRate.toDouble()
        val outLen = (input.size * ratio).toInt().coerceAtLeast(1)
        val out = FloatArray(outLen)
        for (i in 0 until outLen) {
            val srcPos = i / ratio
            val i0 = srcPos.toInt()
            val i1 = (i0 + 1).coerceAtMost(input.size - 1)
            val frac = (srcPos - i0).toFloat()
            out[i] = input[i0] * (1f - frac) + input[i1] * frac
        }
        return out
    }
}
