package cl.vtt.transcriptor

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.provider.OpenableColumns
import android.view.View
import android.widget.ArrayAdapter
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import cl.vtt.transcriptor.databinding.ActivityMainBinding
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class MainActivity : AppCompatActivity() {

    private lateinit var b: ActivityMainBinding
    private val transcriber = Transcriber()

    // Etiquetas visibles e idiomas (código ISO; "" = detección automática).
    private val langLabels = listOf("Español", "Inglés", "Portugués", "Francés", "Detección automática")
    private val langCodes = listOf("es", "en", "pt", "fr", "")

    private var selectedUri: Uri? = null
    private var working = false

    private val pickAudio =
        registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
            if (uri != null) {
                try {
                    contentResolver.takePersistableUriPermission(
                        uri, Intent.FLAG_GRANT_READ_URI_PERMISSION
                    )
                } catch (_: Exception) { /* algunos proveedores no lo permiten */ }
                selectedUri = uri
                b.txtFile.text = displayName(uri)
                b.btnTranscribe.isEnabled = true
            }
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
            val model = b.ddModel.text.toString().takeIf { it in ModelManager.MODELS } ?: "base"
            val langPos = langLabels.indexOf(b.ddLanguage.text.toString()).coerceAtLeast(0)
            prefs.edit()
                .putString("model", model)
                .putInt("lang", langPos)
                .apply()
            startTranscription(uri, model, langCodes[langPos])
        }

        b.btnCopy.setOnClickListener {
            val cm = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
            cm.setPrimaryClip(ClipData.newPlainText("transcripcion", b.txtResult.text.toString()))
            Toast.makeText(this, "Texto copiado", Toast.LENGTH_SHORT).show()
        }

        b.btnShare.setOnClickListener {
            val send = Intent(Intent.ACTION_SEND).apply {
                type = "text/plain"
                putExtra(Intent.EXTRA_TEXT, b.txtResult.text.toString())
            }
            startActivity(Intent.createChooser(send, "Compartir transcripción"))
        }
    }

    private fun startTranscription(uri: Uri, model: String, lang: String) {
        if (working) return
        working = true
        setBusy(true)
        b.txtResult.setText("")
        b.btnCopy.isEnabled = false
        b.btnShare.isEnabled = false

        lifecycleScope.launch {
            try {
                // 1) Asegurar el modelo (descarga solo la primera vez).
                if (!ModelManager.isDownloaded(this@MainActivity, model)) {
                    setStatus("Descargando modelo '$model' (solo la primera vez)…")
                    b.progress.isIndeterminate = false
                } else {
                    b.progress.isIndeterminate = true
                }
                val modelFile = withContext(Dispatchers.IO) {
                    ModelManager.ensureModel(this@MainActivity, model) { pct ->
                        lifecycleScope.launch { b.progress.progress = pct }
                    }
                }

                // 2) Decodificar el audio a PCM 16 kHz mono.
                setStatus("Procesando el audio…")
                b.progress.isIndeterminate = true
                val audio = withContext(Dispatchers.IO) {
                    AudioDecoder.decode(this@MainActivity, uri)
                }
                if (audio.isEmpty()) throw IllegalStateException("No se pudo leer audio del archivo")

                // 3) Cargar el modelo y transcribir en el dispositivo.
                setStatus("Transcribiendo en el dispositivo…")
                val text = withContext(Dispatchers.Default) {
                    transcriber.loadModel(modelFile.absolutePath, model)
                    transcriber.transcribe(audio, lang.ifEmpty { null })
                }

                b.txtResult.setText(text)
                b.btnCopy.isEnabled = text.isNotEmpty()
                b.btnShare.isEnabled = text.isNotEmpty()
                setStatus(if (text.isEmpty()) "No se detectó voz." else "Listo.")
            } catch (e: Exception) {
                setStatus("Error: ${e.message}")
                Toast.makeText(this@MainActivity, e.message ?: "Error", Toast.LENGTH_LONG).show()
            } finally {
                working = false
                setBusy(false)
            }
        }
    }

    private fun setBusy(busy: Boolean) {
        b.progress.visibility = if (busy) View.VISIBLE else View.GONE
        b.btnTranscribe.isEnabled = !busy && selectedUri != null
        b.btnSelect.isEnabled = !busy
        b.tilModel.isEnabled = !busy
        b.tilLanguage.isEnabled = !busy
    }

    private fun setStatus(msg: String) {
        b.txtStatus.text = msg
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

    override fun onDestroy() {
        super.onDestroy()
        transcriber.free()
    }
}
