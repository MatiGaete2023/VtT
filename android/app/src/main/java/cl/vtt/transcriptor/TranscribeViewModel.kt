package cl.vtt.transcriptor

import android.content.Context
import android.net.Uri
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

sealed interface TranscribeUiState {
    data object Idle : TranscribeUiState
    /** progressPct == null -> indeterminado (sin porcentaje conocido todavia). */
    data class Working(val message: String, val progressPct: Int?) : TranscribeUiState
    data class Done(val text: String) : TranscribeUiState
    data class Error(val message: String) : TranscribeUiState
    data object Cancelled : TranscribeUiState
}

/**
 * Posee el trabajo de transcripcion en viewModelScope, que sobrevive a la
 * recreacion de la Activity (p.ej. al rotar la pantalla). Antes, el trabajo
 * corria en lifecycleScope de la Activity: rotar durante una transcripcion
 * cancelaba el scope mientras la llamada nativa (no cooperativa con la
 * cancelacion de corutinas) seguia ejecutandose, y `onDestroy` podia liberar
 * el contexto de whisper.cpp mientras esa llamada todavia lo usaba -> crash
 * nativo (use-after-free). Con el trabajo aqui, la rotacion ya no lo afecta.
 */
class TranscribeViewModel : ViewModel() {

    private val transcriber = Transcriber()

    private val _uiState = MutableStateFlow<TranscribeUiState>(TranscribeUiState.Idle)
    val uiState: StateFlow<TranscribeUiState> = _uiState.asStateFlow()

    private var job: Job? = null
    @Volatile private var cancelSolicitado = false

    val isWorking: Boolean
        get() = job?.isActive == true

    fun transcribe(appContext: Context, uri: Uri, model: String, lang: String) {
        if (isWorking) return
        cancelSolicitado = false
        job = viewModelScope.launch {
            try {
                if (!ModelManager.isDownloaded(appContext, model)) {
                    _uiState.value = TranscribeUiState.Working(
                        "Descargando modelo '$model' (solo la primera vez)…", 0)
                } else {
                    _uiState.value = TranscribeUiState.Working("Preparando…", null)
                }
                val modelFile = withContext(Dispatchers.IO) {
                    ModelManager.ensureModel(appContext, model) { pct ->
                        _uiState.value = TranscribeUiState.Working(
                            "Descargando modelo '$model' (solo la primera vez)…", pct)
                    }
                }

                _uiState.value = TranscribeUiState.Working("Procesando el audio…", null)
                val audio = withContext(Dispatchers.IO) {
                    AudioDecoder.decode(appContext, uri)
                }
                if (audio.isEmpty()) {
                    throw IllegalStateException("No se pudo leer audio del archivo")
                }

                _uiState.value = TranscribeUiState.Working("Transcribiendo en el dispositivo…", 0)
                val text = withContext(Dispatchers.Default) {
                    transcriber.loadModel(modelFile.absolutePath, model)
                    transcriber.transcribe(audio, lang.ifEmpty { null }) { pct ->
                        _uiState.value = TranscribeUiState.Working(
                            "Transcribiendo en el dispositivo…", pct)
                    }
                }

                _uiState.value = if (cancelSolicitado) {
                    TranscribeUiState.Cancelled
                } else {
                    TranscribeUiState.Done(text)
                }
            } catch (e: CancellationException) {
                throw e  // no interferir con la cancelacion estructurada de corutinas
            } catch (e: Exception) {
                _uiState.value = if (cancelSolicitado) {
                    TranscribeUiState.Cancelled
                } else {
                    TranscribeUiState.Error(e.message ?: "Error desconocido")
                }
            }
        }
    }

    /** Pide cancelar la transcripcion en curso. whisper.cpp sondea la bandera
     * de cancelacion durante el computo, asi que se detiene en poco tiempo
     * (no instantaneo). */
    fun cancelar() {
        if (!isWorking) return
        cancelSolicitado = true
        transcriber.requestAbort()
        _uiState.value = TranscribeUiState.Working("Cancelando…", null)
    }

    fun descartarEstadoFinal() {
        if (_uiState.value is TranscribeUiState.Error || _uiState.value is TranscribeUiState.Cancelled) {
            _uiState.value = TranscribeUiState.Idle
        }
    }

    override fun onCleared() {
        super.onCleared()
        // Transcriber.free() es @Synchronized: si una transcripcion sigue en
        // curso, espera a que termine antes de liberar el contexto nativo.
        // Se hace en un hilo aparte para que onCleared() (hilo principal)
        // nunca se bloquee esperando.
        transcriber.requestAbort()
        Thread { transcriber.free() }.start()
    }
}
