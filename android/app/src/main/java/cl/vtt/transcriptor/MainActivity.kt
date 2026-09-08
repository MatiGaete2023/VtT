package cl.vtt.transcriptor

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.OpenableColumns
import android.text.Editable
import android.text.TextWatcher
import android.view.View
import android.view.WindowManager
import android.widget.ArrayAdapter
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import cl.vtt.transcriptor.databinding.ActivityMainBinding
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.OutputStreamWriter
import java.util.Locale

class MainActivity : AppCompatActivity() {

    private lateinit var b: ActivityMainBinding
    private val viewModel: TranscribeViewModel by viewModels()

    // Etiquetas visibles e idiomas (código ISO; "" = detección automática).
    private val langLabels = listOf("Español", "Inglés", "Portugués", "Francés", "Detección automática")
    private val langCodes = listOf("es", "en", "pt", "fr", "")

    private var selectedUri: Uri? = null
    private var actualizandoResultado = false
    private var textoPendienteExportar: String? = null
    private var srtPendienteExportar: String? = null

    private val pickAudio =
        registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
            if (uri != null) tomarUri(uri)
        }

    private val guardarTxt =
        registerForActivityResult(ActivityResultContracts.CreateDocument("text/plain")) { uri ->
            if (uri != null) guardarResultadoEn(uri)
        }

    private val guardarSrt =
        registerForActivityResult(ActivityResultContracts.CreateDocument("application/x-subrip")) { uri ->
            if (uri != null) guardarResultadoSrtEn(uri)
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        b = ActivityMainBinding.inflate(layoutInflater)
        setContentView(b.root)

        val prefs = getSharedPreferences("vtt", Context.MODE_PRIVATE)

        b.ddModel.setAdapter(
            ArrayAdapter(this, android.R.layout.simple_list_item_1, ModelManager.MODELS)
        )
        b.ddLanguage.setAdapter(
            ArrayAdapter(this, android.R.layout.simple_list_item_1, langLabels)
        )

        val savedModel = (prefs.getString("model", "base") ?: "base")
            .takeIf { it in ModelManager.MODELS } ?: "base"
        val savedLangPos = prefs.getInt("lang", 0).coerceIn(0, langLabels.lastIndex)
        b.ddModel.setText(savedModel, false)
        b.ddLanguage.setText(langLabels[savedLangPos], false)

        b.txtResult.addTextChangedListener(object : TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) = Unit
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) = Unit
            override fun afterTextChanged(s: Editable?) {
                if (!actualizandoResultado) {
                    viewModel.actualizarTextoEditado(applicationContext, s?.toString() ?: "")
                }
            }
        })

        b.btnSelect.setOnClickListener {
            pickAudio.launch(arrayOf("audio/*", "video/*"))
        }

        b.btnTranscribe.setOnClickListener {
            val uri = selectedUri ?: return@setOnClickListener
            if (viewModel.isWorking) return@setOnClickListener
            val model = b.ddModel.text.toString().takeIf { it in ModelManager.MODELS } ?: "base"
            val langPos = langLabels.indexOf(b.ddLanguage.text.toString()).coerceAtLeast(0)
            prefs.edit()
                .putString("model", model)
                .putInt("lang", langPos)
                .apply()
            actualizandoResultado = true
            b.txtResult.setText("")
            actualizandoResultado = false
            viewModel.transcribe(
                applicationContext,
                uri,
                model,
                langCodes[langPos],
                displayName(uri)
            )
        }

        b.btnCancel.setOnClickListener {
            viewModel.cancelar()
        }

        b.btnCopy.setOnClickListener {
            val cm = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
            cm.setPrimaryClip(ClipData.newPlainText("transcripcion", b.txtResult.text.toString()))
            Toast.makeText(this, "Texto copiado", Toast.LENGTH_SHORT).show()
        }

        b.btnSave.setOnClickListener {
            textoPendienteExportar = b.txtResult.text.toString()
            val base = nombreBaseActual()
            guardarTxt.launch("$base.txt")
        }

        b.btnSaveTimed.setOnClickListener {
            val estado = viewModel.uiState.value as? TranscribeUiState.Done ?: return@setOnClickListener
            if (estado.editedText != null) {
                Toast.makeText(this, "El SRT conserva el texto original por segmento. Revisa o deshaz la edición antes de exportarlo.", Toast.LENGTH_LONG).show()
                return@setOnClickListener
            }
            srtPendienteExportar = construirSrt(estado)
            val base = nombreBaseActual()
            guardarSrt.launch("$base.srt")
        }

        b.btnShare.setOnClickListener {
            val send = Intent(Intent.ACTION_SEND).apply {
                type = "text/plain"
                putExtra(Intent.EXTRA_TEXT, b.txtResult.text.toString())
            }
            startActivity(Intent.createChooser(send, "Compartir transcripción"))
        }

        manejarIntentEntrante(intent)

        lifecycleScope.launch {
            repeatOnLifecycle(Lifecycle.State.STARTED) {
                viewModel.uiState.collect { estado -> render(estado) }
            }
        }
        viewModel.restaurar(applicationContext)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        manejarIntentEntrante(intent)
    }

    /** Recibe audio/video compartido desde otra app ("Compartir" -> Transcriptor VtT). */
    private fun manejarIntentEntrante(intent: Intent) {
        val uri: Uri? = when (intent.action) {
            Intent.ACTION_SEND ->
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                    intent.getParcelableExtra(Intent.EXTRA_STREAM, Uri::class.java)
                } else {
                    @Suppress("DEPRECATION")
                    intent.getParcelableExtra(Intent.EXTRA_STREAM)
                }
            Intent.ACTION_VIEW -> intent.data
            else -> null
        }
        if (uri != null) tomarUri(uri)
    }

    private fun tomarUri(uri: Uri) {
        if (viewModel.isWorking) {
            Toast.makeText(
                this,
                "Espera a que termine o cancela la transcripción actual",
                Toast.LENGTH_SHORT
            ).show()
            return
        }
        try {
            contentResolver.takePersistableUriPermission(
                uri, Intent.FLAG_GRANT_READ_URI_PERMISSION
            )
        } catch (_: Exception) { /* algunos proveedores (p.ej. de otra app) no lo permiten */ }
        viewModel.prepararNuevaFuente()
        selectedUri = uri
        b.txtFile.text = displayName(uri)
        actualizandoResultado = true
        b.txtResult.setText("")
        actualizandoResultado = false
        b.btnCopy.isEnabled = false
        b.btnSave.isEnabled = false
        b.btnSaveTimed.isEnabled = false
        b.btnShare.isEnabled = false
        b.btnTranscribe.isEnabled = !viewModel.isWorking
    }

    private fun guardarResultadoEn(uri: Uri) {
        val texto = envolverTexto(textoPendienteExportar ?: return)
        textoPendienteExportar = null
        lifecycleScope.launch {
            val ok = withContext(Dispatchers.IO) {
                try {
                    val out = contentResolver.openOutputStream(uri)
                        ?: return@withContext false
                    out.use {
                        OutputStreamWriter(it, Charsets.UTF_8).use { writer -> writer.write(texto) }
                    }
                    true
                } catch (_: Exception) {
                    false
                }
            }
            Toast.makeText(
                this@MainActivity,
                if (ok) "Transcripción guardada" else "No se pudo guardar el archivo",
                Toast.LENGTH_SHORT
            ).show()
        }
    }

    private fun guardarResultadoSrtEn(uri: Uri) {
        val texto = srtPendienteExportar ?: return
        srtPendienteExportar = null
        lifecycleScope.launch {
            val ok = withContext(Dispatchers.IO) {
                try {
                    val out = contentResolver.openOutputStream(uri)
                        ?: return@withContext false
                    out.use { OutputStreamWriter(it, Charsets.UTF_8).use { writer -> writer.write(texto) } }
                    true
                } catch (_: Exception) {
                    false
                }
            }
            Toast.makeText(
                this@MainActivity,
                if (ok) "Subtítulos guardados" else "No se pudo guardar el archivo",
                Toast.LENGTH_SHORT
            ).show()
        }
    }

    private fun construirSrt(estado: TranscribeUiState.Done): String =
        estado.segments.mapIndexed { index, segmento ->
            (index + 1).toString() + "\n" +
                marcaSrt(segmento.startMs) + " --> " + marcaSrt(segmento.endMs) + "\n" +
                segmento.text.trim() + "\n"
        }.joinToString("\n")

    private fun nombreBaseActual(): String {
        val estado = viewModel.uiState.value as? TranscribeUiState.Done
        val nombre = estado?.sourceName ?: selectedUri?.let(::displayName) ?: "transcripcion"
        return nombre.substringBeforeLast('.').ifBlank { "transcripcion" }
    }

    private fun marcaSrt(milisegundos: Long): String {
        val total = milisegundos.coerceAtLeast(0L)
        val horas = total / 3_600_000
        val minutos = (total % 3_600_000) / 60_000
        val segundos = (total % 60_000) / 1_000
        val ms = total % 1_000
        return String.format(Locale.ROOT, "%02d:%02d:%02d,%03d", horas, minutos, segundos, ms)
    }

    /** Ajusta el texto a ~100 columnas, igual que la version de escritorio,
     * para que se pueda leer sin desplazarse hacia el lado. */
    private fun envolverTexto(texto: String, ancho: Int = 100): String {
        return texto.split("\n").joinToString("\n") { parrafo ->
            if (parrafo.isBlank()) return@joinToString parrafo
            val palabras = parrafo.split(" ")
            val lineas = mutableListOf<StringBuilder>(StringBuilder())
            for (palabra in palabras) {
                val actual = lineas.last()
                val nuevoLargo = (if (actual.isEmpty()) 0 else actual.length + 1) + palabra.length
                if (nuevoLargo > ancho && actual.isNotEmpty()) {
                    lineas.add(StringBuilder(palabra))
                } else {
                    if (actual.isNotEmpty()) actual.append(' ')
                    actual.append(palabra)
                }
            }
            lineas.joinToString("\n")
        }
    }

    private fun render(estado: TranscribeUiState) {
        when (estado) {
            is TranscribeUiState.Idle -> {
                // No toca txtStatus: si Idle llega tras descartarEstadoFinal()
                // (después de un error o cancelación), el mensaje debe quedar
                // visible hasta la próxima acción, no taparse con "Listo.".
                setBusy(false)
            }
            is TranscribeUiState.Working -> {
                setBusy(true)
                b.txtStatus.text = estado.message
                b.btnCopy.isEnabled = false
                b.btnSave.isEnabled = false
                b.btnSaveTimed.isEnabled = false
                b.btnShare.isEnabled = false
                if (estado.progressPct != null) {
                    b.progress.isIndeterminate = false
                    b.progress.progress = estado.progressPct
                } else {
                    b.progress.isIndeterminate = true
                }
            }
            is TranscribeUiState.Done -> {
                setBusy(false)
                val texto = estado.editedText ?: estado.text
                if (b.txtResult.text.toString() != texto) {
                    actualizandoResultado = true
                    b.txtResult.setText(texto)
                    actualizandoResultado = false
                }
                b.btnCopy.isEnabled = texto.isNotEmpty()
                b.btnSave.isEnabled = texto.isNotEmpty()
                b.btnSaveTimed.isEnabled = texto.isNotEmpty() && estado.segments.isNotEmpty()
                b.btnShare.isEnabled = texto.isNotEmpty()
                b.txtStatus.text = if (texto.isEmpty()) "No se detectó voz." else "Listo."
            }
            is TranscribeUiState.Cancelled -> {
                setBusy(false)
                b.txtStatus.text = getString(R.string.cancelled)
                viewModel.descartarEstadoFinal()
            }
            is TranscribeUiState.Error -> {
                setBusy(false)
                b.txtStatus.text = "Error: ${estado.message}"
                Toast.makeText(this, estado.message, Toast.LENGTH_LONG).show()
                viewModel.descartarEstadoFinal()
            }
        }
    }

    private fun setBusy(busy: Boolean) {
        b.progress.visibility = if (busy) View.VISIBLE else View.GONE
        b.btnCancel.visibility = if (busy) View.VISIBLE else View.GONE
        b.btnCancel.isEnabled = busy
        b.btnTranscribe.isEnabled = !busy && selectedUri != null
        b.btnSelect.isEnabled = !busy
        b.tilModel.isEnabled = !busy
        b.tilLanguage.isEnabled = !busy
        // Evita que la pantalla se apague durante una transcripcion larga.
        if (busy) {
            window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        } else {
            window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        }
    }

    private fun displayName(uri: Uri): String {
        var name = uri.lastPathSegment ?: "audio"
        try {
            contentResolver.query(uri, null, null, null, null)?.use { c ->
                val idx = c.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                if (idx >= 0 && c.moveToFirst()) name = c.getString(idx)
            }
        } catch (_: Exception) { /* usar el respaldo */ }
        return name
    }
}
