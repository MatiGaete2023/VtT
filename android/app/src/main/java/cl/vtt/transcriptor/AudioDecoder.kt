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
import kotlin.math.ceil
import kotlin.math.max
import kotlin.math.min

/**
 * Decodifica audio/video soportado por Android a PCM float mono 16 kHz.
 *
 * `decode()` se conserva para archivos cortos. `decodeRange()` limita el PCM
 * intermedio a una ventana temporal y permite que TranscribeViewModel procese
 * audios largos por bloques sin mantener horas completas en memoria.
 */
object AudioDecoder {

    const val TARGET_RATE = 16_000

    private class Pcm(val bytes: ByteArray, val sampleRate: Int, val channels: Int)

    fun duracionSegundos(context: Context, uri: Uri): Long? {
        val retriever = MediaMetadataRetriever()
        return try {
            retriever.setDataSource(context, uri)
            retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION)
                ?.toLongOrNull()?.let { it / 1000 }
        } catch (_: Exception) {
            null
        } finally {
            try { retriever.release() } catch (_: Exception) { }
        }
    }

    fun decode(
        context: Context,
        uri: Uri,
        isCancelled: () -> Boolean = { false }
    ): FloatArray {
        val extractor = MediaExtractor()
        return try {
            val pfd = context.contentResolver.openFileDescriptor(uri, "r")
                ?: throw IllegalArgumentException("No se pudo abrir el archivo de audio")
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
                val pcm = decodePcm16(
                    extractor, format, mime, srcRate, srcChannels, isCancelled
                )
                pcmToTarget(pcm)
            }
        } finally {
            try { extractor.release() } catch (_: Exception) { }
        }
    }

    /**
     * Decodifica solo [startMs, endMs). Se usa en archivos largos. MediaExtractor
     * puede buscar un frame de sincronización anterior, por lo que el decoder
     * recorta el PCM de salida usando presentationTimeUs antes de retornarlo.
     */
    fun decodeRange(
        context: Context,
        uri: Uri,
        startMs: Long,
        endMs: Long,
        isCancelled: () -> Boolean = { false }
    ): FloatArray {
        require(startMs >= 0 && endMs > startMs) { "Rango de audio inválido" }
        val extractor = MediaExtractor()
        return try {
            val pfd = context.contentResolver.openFileDescriptor(uri, "r")
                ?: throw IllegalArgumentException("No se pudo abrir el archivo de audio")
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
                val startUs = startMs * 1000L
                val endUs = endMs * 1000L
                extractor.seekTo(startUs, MediaExtractor.SEEK_TO_PREVIOUS_SYNC)
                val pcm = decodePcm16Range(
                    extractor, format, mime, srcRate, srcChannels,
                    startUs, endUs, isCancelled
                )
                pcmToTarget(pcm)
            }
        } finally {
            try { extractor.release() } catch (_: Exception) { }
        }
    }

    private fun pcmToTarget(pcm: Pcm): FloatArray {
        if (pcm.bytes.isEmpty()) return FloatArray(0)
        val shorts = ShortArray(pcm.bytes.size / 2)
        ByteBuffer.wrap(pcm.bytes).order(ByteOrder.LITTLE_ENDIAN)
            .asShortBuffer().get(shorts)
        val mono = downmixToMono(shorts, pcm.channels)
        return resample(mono, pcm.sampleRate, TARGET_RATE)
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
        fallbackChannels: Int,
        isCancelled: () -> Boolean
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
                if (isCancelled()) {
                    throw java.util.concurrent.CancellationException("decodificación cancelada")
                }
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
                            codec.queueInputBuffer(
                                inIndex, 0, sampleSize, extractor.sampleTime, 0
                            )
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
                        val values = outputFormat(codec, fallbackRate, fallbackChannels)
                        outRate = values.first
                        outChannels = values.second
                    }
                }
            }
            return Pcm(bos.toByteArray(), outRate, outChannels)
        } finally {
            try { codec.stop() } catch (_: Exception) { }
            try { codec.release() } catch (_: Exception) { }
        }
    }

    private fun decodePcm16Range(
        extractor: MediaExtractor,
        inputFormat: MediaFormat,
        mime: String,
        fallbackRate: Int,
        fallbackChannels: Int,
        startUs: Long,
        endUs: Long,
        isCancelled: () -> Boolean
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
                if (isCancelled()) {
                    throw java.util.concurrent.CancellationException("decodificación cancelada")
                }
                if (!sawInputEOS) {
                    val inIndex = codec.dequeueInputBuffer(timeoutUs)
                    if (inIndex >= 0) {
                        val inputBuffer = codec.getInputBuffer(inIndex)!!
                        val sampleTime = extractor.sampleTime
                        if (sampleTime < 0 || sampleTime >= endUs) {
                            codec.queueInputBuffer(
                                inIndex, 0, 0,
                                if (sampleTime > 0) sampleTime else endUs,
                                MediaCodec.BUFFER_FLAG_END_OF_STREAM
                            )
                            sawInputEOS = true
                        } else {
                            val sampleSize = extractor.readSampleData(inputBuffer, 0)
                            if (sampleSize < 0) {
                                codec.queueInputBuffer(
                                    inIndex, 0, 0, sampleTime.coerceAtLeast(0),
                                    MediaCodec.BUFFER_FLAG_END_OF_STREAM
                                )
                                sawInputEOS = true
                            } else {
                                codec.queueInputBuffer(
                                    inIndex, 0, sampleSize, sampleTime, 0
                                )
                                extractor.advance()
                            }
                        }
                    }
                }

                val outIndex = codec.dequeueOutputBuffer(info, timeoutUs)
                when {
                    outIndex >= 0 -> {
                        if (info.size > 0 && outRate > 0 && outChannels > 0) {
                            val outputBuffer = codec.getOutputBuffer(outIndex)
                            if (outputBuffer != null) {
                                val bytesPerFrame = outChannels * 2
                                val frames = info.size / bytesPerFrame
                                val bufferStartUs = info.presentationTimeUs
                                val bufferEndUs = bufferStartUs +
                                    (frames.toLong() * 1_000_000L / outRate.toLong())
                                val keepStartUs = max(startUs, bufferStartUs)
                                val keepEndUs = min(endUs, bufferEndUs)
                                if (keepEndUs > keepStartUs) {
                                    val firstFrame = max(
                                        0,
                                        (((keepStartUs - bufferStartUs).toDouble() * outRate) /
                                            1_000_000.0).toInt()
                                    )
                                    val lastFrame = min(
                                        frames,
                                        ceil(
                                            ((keepEndUs - bufferStartUs).toDouble() * outRate) /
                                                1_000_000.0
                                        ).toInt()
                                    )
                                    if (lastFrame > firstFrame) {
                                        val byteStart = info.offset + firstFrame * bytesPerFrame
                                        val byteEnd = info.offset + lastFrame * bytesPerFrame
                                        outputBuffer.position(byteStart)
                                        outputBuffer.limit(min(info.offset + info.size, byteEnd))
                                        val chunk = ByteArray(outputBuffer.remaining())
                                        outputBuffer.get(chunk)
                                        bos.write(chunk)
                                    }
                                }
                            }
                        }
                        codec.releaseOutputBuffer(outIndex, false)
                        if (info.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM != 0) {
                            sawOutputEOS = true
                        }
                    }
                    outIndex == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED -> {
                        val values = outputFormat(codec, fallbackRate, fallbackChannels)
                        outRate = values.first
                        outChannels = values.second
                    }
                }
            }
            return Pcm(bos.toByteArray(), outRate, outChannels)
        } finally {
            try { codec.stop() } catch (_: Exception) { }
            try { codec.release() } catch (_: Exception) { }
        }
    }

    private fun outputFormat(
        codec: MediaCodec,
        fallbackRate: Int,
        fallbackChannels: Int
    ): Pair<Int, Int> {
        val of = codec.outputFormat
        val rate = if (of.containsKey(MediaFormat.KEY_SAMPLE_RATE)) {
            of.getInteger(MediaFormat.KEY_SAMPLE_RATE)
        } else fallbackRate
        val channels = if (of.containsKey(MediaFormat.KEY_CHANNEL_COUNT)) {
            of.getInteger(MediaFormat.KEY_CHANNEL_COUNT)
        } else fallbackChannels
        val encoding = if (of.containsKey(MediaFormat.KEY_PCM_ENCODING)) {
            of.getInteger(MediaFormat.KEY_PCM_ENCODING)
        } else android.media.AudioFormat.ENCODING_PCM_16BIT
        require(encoding == android.media.AudioFormat.ENCODING_PCM_16BIT) {
            "El decodificador entregó PCM no compatible"
        }
        return rate to channels
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
