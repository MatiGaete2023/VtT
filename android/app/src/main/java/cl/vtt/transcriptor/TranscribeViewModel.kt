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

sealed interface TranscribeUiState {
    data object Idle : TranscribeUiState
    /** progressPct == null -> indeterminado (sin porcentaje conocido todavia). */
    data class Working(val message: String, val progressPct: Int?) : TranscribeUiState
    data class Done(
        val text: String,
        /** Texto revisado por el usuario; null significa que aún no se editó. */
        val editedText: String? = null,
        val sourceName: String? = null,
        val segments: List<TranscriptionSegment> = emptyList()
    ) : TranscribeUiState
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

    companion object {
        private const val UMBRAL_AUDIO_LARGO_S = 90 * 60L  // 90 min
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
        ultimoModelo = model
        ultimoIdioma = lang
        ultimoOrigen = sourceName
        job = viewModelScope.launch {
            try {
                if (!ModelManager.isDownloaded(appContext, model)) {
                    _uiState.value = TranscribeUiState.Working(
                        "Descargando modelo '$model' (solo la primera vez)…", 0)
                } else {
                    _uiState.value = TranscribeUiState.Working("Preparando…", null)
                }
                val modelFile = withContext(Dispatchers.IO) {
                    ModelManager.ensureModel(appContext, model, isCancelled = { cancelSolicitado }) { pct ->
                        _uiState.value = TranscribeUiState.Working(
                            "Descargando modelo '$model' (solo la primera vez)…", pct)
                    }
                }
                if (cancelSolicitado) throw java.util.concurrent.CancellationException("cancelada")

                val duracion = withContext(Dispatchers.IO) {
                    AudioDecoder.duracionSegundos(appContext, uri)
                }
                val avisoLargo = if (duracion != null && duracion > UMBRAL_AUDIO_LARGO_S) {
                    " (~${duracion / 60} min, puede tardar y usar bastante memoria)"
                } else {
                    ""
                }
                _uiState.value = TranscribeUiState.Working("Procesando el audio…$avisoLargo", null)
                val audio = withContext(Dispatchers.IO) {
                    AudioDecoder.decode(appContext, uri)
                }
                if (cancelSolicitado) throw java.util.concurrent.CancellationException("cancelada")
                if (audio.isEmpty()) {
                    throw IllegalStateException("No se pudo leer audio del archivo")
                }

                _uiState.value = TranscribeUiState.Working("Transcribiendo en el dispositivo…", 0)
                val resultado = withContext(Dispatchers.Default) {
                    if (cancelSolicitado) throw java.util.concurrent.CancellationException("cancelada")
                    transcriber.loadModel(modelFile.absolutePath, model)
                    transcriber.transcribe(audio, lang.ifEmpty { null }) { pct ->
                        _uiState.value = TranscribeUiState.Working(
                            "Transcribiendo en el dispositivo…", pct)
                    }
                }

                if (cancelSolicitado) {
                    _uiState.value = TranscribeUiState.Cancelled
                } else {
                    _uiState.value = TranscribeUiState.Done(
                        resultado.text,
                        sourceName = sourceName,
                        segments = resultado.segments
                    )
                    viewModelScope.launch(Dispatchers.IO) {
                        TranscriptionStore.save(
                            appContext,
                            resultado.text,
                            null,
                            sourceName,
                            model,
                            lang,
                            resultado.segments
                        )
                    }
                }
            } catch (e: CancellationException) {
                if (cancelSolicitado) {
                    _uiState.value = TranscribeUiState.Cancelled
                } else {
                    throw e  // cancelación estructurada del ViewModel
                }
            } catch (e: OutOfMemoryError) {
                // Un audio muy largo (horas) puede agotar la memoria del proceso:
                // decodificarlo entero a PCM float ocupa varias veces su duracion en
                // MB. OutOfMemoryError es un Error, no una Exception, así que sin este
                // catch especifico se escapaba del try/catch de abajo y tumbaba la app.
                _uiState.value = TranscribeUiState.Error(
                    "El audio es demasiado largo para la memoria disponible. " +
                    "Prueba con un archivo más corto o un modelo más liviano (tiny/base).")
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

    /** Conserva una edición humana separada del texto original del motor. */
    fun actualizarTextoEditado(appContext: Context, texto: String) {
        val estado = _uiState.value as? TranscribeUiState.Done ?: return
        val editado = texto.takeIf { it != estado.text }
        _uiState.value = estado.copy(editedText = editado)
        guardadoEditado?.cancel()
        guardadoEditado = viewModelScope.launch(Dispatchers.IO) {
            delay(250)
            TranscriptionStore.save(
                appContext,
                estado.text,
                editado,
                estado.sourceName ?: ultimoOrigen,
                ultimoModelo,
                ultimoIdioma,
                estado.segments
            )
        }
    }

    /** Recupera el último documento si Android terminó el proceso. */
    fun restaurar(appContext: Context) {
        if (_uiState.value !is TranscribeUiState.Idle || isWorking) return
        viewModelScope.launch(Dispatchers.IO) {
            val guardado = TranscriptionStore.load(appContext) ?: return@launch
            ultimoModelo = guardado.model
            ultimoIdioma = guardado.language
            ultimoOrigen = guardado.sourceName
            _uiState.value = TranscribeUiState.Done(
                guardado.original,
                guardado.edited,
                guardado.sourceName,
                guardado.segments
            )
        }
    }

    fun descartarEstadoFinal() {
        if (_uiState.value is TranscribeUiState.Error || _uiState.value is TranscribeUiState.Cancelled) {
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
        // Transcriber.free() es @Synchronized: si una transcripcion sigue en
        // curso, espera a que termine antes de liberar el contexto nativo.
        // Se hace en un hilo aparte para que onCleared() (hilo principal)
        // nunca se bloquee esperando.
        cancelSolicitado = true
        transcriber.requestAbort()
        Thread { transcriber.free() }.start()
    }
}
