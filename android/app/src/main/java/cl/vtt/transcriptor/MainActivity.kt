package cl.vtt.transcriptor

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.OpenableColumns
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

class MainActivity : AppCompatActivity() {

    private lateinit var b: ActivityMainBinding
    private val viewModel: TranscribeViewModel by viewModels()

    // Etiquetas visibles e idiomas (código ISO; "" = detección automática).
    private val langLabels = listOf("Español", "Inglés", "Portugués", "Francés", "Detección automática")
    private val langCodes = listOf("es", "en", "pt", "fr", "")

    private var selectedUri: Uri? = null

    private val pickAudio =
        registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
            if (uri != null) tomarUri(uri)
        }

    private val guardarTxt =
        registerForActivityResult(ActivityResultContracts.CreateDocument("text/plain")) { uri ->
            if (uri != null) guardarResultadoEn(uri)
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
            b.txtResult.setText("")
            viewModel.transcribe(applicationContext, uri, model, langCodes[langPos])
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
            val base = selectedUri?.let { displayName(it).substringBeforeLast('.') } ?: "transcripcion"
            guardarTxt.launch("$base.txt")
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
        try {
            contentResolver.takePersistableUriPermission(
                uri, Intent.FLAG_GRANT_READ_URI_PERMISSION
            )
        } catch (_: Exception) { /* algunos proveedores (p.ej. de otra app) no lo permiten */ }
        selectedUri = uri
        b.txtFile.text = displayName(uri)
        b.btnTranscribe.isEnabled = !viewModel.isWorking
    }

    private fun guardarResultadoEn(uri: Uri) {
        val texto = envolverTexto(b.txtResult.text.toString())
        lifecycleScope.launch {
            val ok = withContext(Dispatchers.IO) {
                try {
                    contentResolver.openOutputStream(uri)?.use { out ->
                        OutputStreamWriter(out, Charsets.UTF_8).use { it.write(texto) }
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
                b.txtResult.setText(estado.text)
                b.btnCopy.isEnabled = estado.text.isNotEmpty()
                b.btnSave.isEnabled = estado.text.isNotEmpty()
                b.btnShare.isEnabled = estado.text.isNotEmpty()
                b.txtStatus.text = if (estado.text.isEmpty()) "No se detectó voz." else "Listo."
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
