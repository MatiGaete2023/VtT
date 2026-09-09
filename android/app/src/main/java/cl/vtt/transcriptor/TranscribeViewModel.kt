package cl.vtt.transcriptor

import android.content.Context
import android.net.Uri
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlin.math.ceil

sealed interface TranscribeUiState {
    data object Idle : TranscribeUiState
    data class Working(val message: String, val progressPct: Int?) : TranscribeUiState
    data class Done(
        val text: String,
        val editedText: String? = null,
        val sourceName: String? = null,
        val segments: List<TranscriptionSegment> = emptyList()
    ) : TranscribeUiState
    data class Error(val message: String) : TranscribeUiState
    data object Cancelled : TranscribeUiState
}

/**
 * Posee el trabajo de transcripcion en viewModelScope, que sobrevive a la
 * recreacion de la Activity. Los archivos largos se procesan por ventanas
 * solapadas para no materializar horas completas de PCM en memoria.
 */
class TranscribeViewModel : ViewModel() {

    companion object {
        // Sobre este umbral se prioriza memoria acotada. whisper.cpp ya usa
        // no_context=true, por lo que el corte no pierde un contexto global que
        // antes estuviera activo.
        private const val CHUNKED_THRESHOLD_S = 5 * 60L
        private const val CHUNK_MS = 90_000L
        private const val OVERLAP_MS = 2_000L
    }

    private val transcriber = Transcriber()

    private val _uiState = MutableStateFlow<TranscribeUiState>(TranscribeUiState.Idle)
    val uiState: StateFlow<TranscribeUiState> = _uiState.asStateFlow()

    private var job: Job? = null
    @Volatile private var cancelSolicitado = false
    private var ultimoModelo = "base"
    private var ultimoIdioma = ""
    private var ultimoOrigen: String? = null
    private var guardadoEditado: Job? = null

    val isWorking: Boolean
        get() = job?.isActive == true

    fun transcribe(
        appContext: Context,
        uri: Uri,
        model: String,
        lang: String,
        sourceName: String? = null
    ) {
        if (isWorking) return
        cancelSolicitado = false
        transcriber.resetAbort()
        ultimoModelo = model
        ultimoIdioma = lang
        ultimoOrigen = sourceName
        job = viewModelScope.launch {
            try {
                _uiState.value = TranscribeUiState.Working("Comprobando el modelo…", null)
                val modeloDisponible = withContext(Dispatchers.IO) {
                    ModelManager.isDownloaded(appContext, model)
                }
                if (!modeloDisponible) {
                    _uiState.value = TranscribeUiState.Working(
                        "Descargando modelo '$model' (solo la primera vez)…", 0
                    )
                } else {
                    _uiState.value = TranscribeUiState.Working("Preparando…", null)
                }
                val modelFile = withContext(Dispatchers.IO) {
                    ModelManager.ensureModel(
                        appContext, model, isCancelled = { cancelSolicitado }
                    ) { pct ->
                        _uiState.value = TranscribeUiState.Working(
                            "Descargando modelo '$model' (solo la primera vez)…", pct
                        )
                    }
                }
                if (cancelSolicitado) {
                    throw java.util.concurrent.CancellationException("cancelada")
                }

                val duracion = withContext(Dispatchers.IO) {
                    AudioDecoder.duracionSegundos(appContext, uri)
                }
                val resultado = if (duracion != null && duracion > CHUNKED_THRESHOLD_S) {
                    transcribirPorBloques(
                        appContext, uri, modelFile.absolutePath, model,
                        lang.ifEmpty { null }, duracion * 1000L
                    )
                } else {
                    transcribirArchivoCorto(
                        appContext, uri, modelFile.absolutePath, model,
                        lang.ifEmpty { null }
                    )
                }

                if (cancelSolicitado) {
                    _uiState.value = TranscribeUiState.Cancelled
                } else {
                    withContext(Dispatchers.IO) {
                        TranscriptionStore.save(
                            appContext, resultado.text, null, sourceName,
                            model, lang, resultado.segments
                        )
                    }
                    if (cancelSolicitado) {
                        throw java.util.concurrent.CancellationException("cancelada")
                    }
                    _uiState.value = TranscribeUiState.Done(
                        resultado.text,
                        sourceName = sourceName,
                        segments = resultado.segments
                    )
                }
            } catch (e: CancellationException) {
                if (cancelSolicitado) {
                    _uiState.value = TranscribeUiState.Cancelled
                } else {
                    throw e
                }
            } catch (e: OutOfMemoryError) {
                _uiState.value = TranscribeUiState.Error(
                    "No hay memoria suficiente para procesar este bloque de audio. " +
                    "Prueba con un modelo más liviano (tiny/base)."
                )
            } catch (e: Exception) {
                _uiState.value = if (cancelSolicitado) {
                    TranscribeUiState.Cancelled
                } else {
                    TranscribeUiState.Error(e.message ?: "Error desconocido")
                }
            }
        }
    }

    private suspend fun transcribirArchivoCorto(
        appContext: Context,
        uri: Uri,
        modelPath: String,
        model: String,
        lang: String?
    ): TranscriptionResult {
        _uiState.value = TranscribeUiState.Working("Procesando el audio…", null)
        val audio = withContext(Dispatchers.IO) {
            AudioDecoder.decode(appContext, uri) { cancelSolicitado }
        }
        if (cancelSolicitado) {
            throw java.util.concurrent.CancellationException("cancelada")
        }
        if (audio.isEmpty()) throw IllegalStateException("No se pudo leer audio del archivo")

        _uiState.value = TranscribeUiState.Working("Transcribiendo en el dispositivo…", 0)
        return withContext(Dispatchers.Default) {
            if (cancelSolicitado) {
                throw java.util.concurrent.CancellationException("cancelada")
            }
            transcriber.loadModel(modelPath, model)
            if (cancelSolicitado) {
                throw java.util.concurrent.CancellationException("cancelada")
            }
            transcriber.transcribe(audio, lang) { pct ->
                _uiState.value = TranscribeUiState.Working(
                    "Transcribiendo en el dispositivo…", pct
                )
            }
        }
    }

    private suspend fun transcribirPorBloques(
        appContext: Context,
        uri: Uri,
        modelPath: String,
        model: String,
        lang: String?,
        durationMs: Long
    ): TranscriptionResult {
        require(durationMs > 0)
        withContext(Dispatchers.Default) {
            transcriber.loadModel(modelPath, model)
        }
        val stepMs = CHUNK_MS - OVERLAP_MS
        val totalChunks = maxOf(
            1,
            ceil(maxOf(0L, durationMs - OVERLAP_MS).toDouble() / stepMs).toInt()
        )
        val merged = mutableListOf<TranscriptionSegment>()
        var chunkIndex = 0
        var startMs = 0L

        while (startMs < durationMs) {
            if (cancelSolicitado) {
                throw java.util.concurrent.CancellationException("cancelada")
            }
            val endMs = minOf(durationMs, startMs + CHUNK_MS)
            val basePct = ((chunkIndex.toDouble() / totalChunks) * 100).toInt()
            _uiState.value = TranscribeUiState.Working(
                "Procesando bloque ${chunkIndex + 1}/$totalChunks…", basePct
            )
            val audio = withContext(Dispatchers.IO) {
                AudioDecoder.decodeRange(
                    appContext, uri, startMs, endMs
                ) { cancelSolicitado }
            }
            if (audio.isEmpty()) {
                throw IllegalStateException(
                    "No se pudo leer el bloque ${chunkIndex + 1} del audio"
                )
            }
            val currentIndex = chunkIndex
            val result = withContext(Dispatchers.Default) {
                transcriber.transcribe(audio, lang) { localPct ->
                    val overall = (((currentIndex + localPct / 100.0) /
                        totalChunks.toDouble()) * 100.0).toInt().coerceIn(0, 100)
                    _uiState.value = TranscribeUiState.Working(
                        "Transcribiendo bloque ${currentIndex + 1}/$totalChunks…",
                        overall
                    )
                }
            }

            val cutMs = if (chunkIndex == 0) Long.MIN_VALUE else startMs + OVERLAP_MS / 2
            if (chunkIndex > 0) {
                merged.removeAll { segmentMidpoint(it) >= cutMs }
            }
            for (segment in result.segments) {
                val shifted = shiftSegment(segment, startMs)
                if (segmentMidpoint(shifted) >= cutMs) {
                    merged += shifted
                }
            }

            if (endMs >= durationMs) break
            chunkIndex += 1
            startMs += stepMs
        }

        merged.sortBy { it.startMs }
        val text = merged.joinToString(" ") { it.text.trim() }
            .replace(Regex("\\s+"), " ")
            .trim()
        _uiState.value = TranscribeUiState.Working(
            "Uniendo bloques…", 100
        )
        return TranscriptionResult(text, merged)
    }

    private fun segmentMidpoint(segment: TranscriptionSegment): Long =
        segment.startMs + (segment.endMs - segment.startMs).coerceAtLeast(0L) / 2

    private fun shiftSegment(segment: TranscriptionSegment, offsetMs: Long): TranscriptionSegment =
        segment.copy(
            startMs = segment.startMs + offsetMs,
            endMs = segment.endMs + offsetMs,
            words = segment.words.map { word ->
                word.copy(
                    startMs = word.startMs?.plus(offsetMs),
                    endMs = word.endMs?.plus(offsetMs)
                )
            }
        )

    fun cancelar() {
        if (!isWorking) return
        cancelSolicitado = true
        transcriber.requestAbort()
        _uiState.value = TranscribeUiState.Working("Cancelando…", null)
    }

    fun actualizarTextoEditado(appContext: Context, texto: String) {
        val estado = _uiState.value as? TranscribeUiState.Done ?: return
        val editado = texto.takeIf { it != estado.text }
        _uiState.value = estado.copy(editedText = editado)
        guardadoEditado?.cancel()
        guardadoEditado = viewModelScope.launch(Dispatchers.IO) {
            delay(250)
            TranscriptionStore.save(
                appContext, estado.text, editado,
                estado.sourceName ?: ultimoOrigen,
                ultimoModelo, ultimoIdioma, estado.segments
            )
        }
    }

    fun restaurar(appContext: Context) {
        if (_uiState.value !is TranscribeUiState.Idle || isWorking) return
        viewModelScope.launch(Dispatchers.IO) {
            val guardado = TranscriptionStore.load(appContext) ?: return@launch
            ultimoModelo = guardado.model
            ultimoIdioma = guardado.language
            ultimoOrigen = guardado.sourceName
            _uiState.value = TranscribeUiState.Done(
                guardado.original, guardado.edited,
                guardado.sourceName, guardado.segments
            )
        }
    }

    fun descartarEstadoFinal() {
        if (_uiState.value is TranscribeUiState.Error ||
            _uiState.value is TranscribeUiState.Cancelled) {
            _uiState.value = TranscribeUiState.Idle
        }
    }

    fun prepararNuevaFuente() {
        if (!isWorking && _uiState.value is TranscribeUiState.Done) {
            _uiState.value = TranscribeUiState.Idle
        }
    }

    override fun onCleared() {
        super.onCleared()
        cancelSolicitado = true
        transcriber.requestAbort()
        Thread { transcriber.free() }.start()
    }
}
