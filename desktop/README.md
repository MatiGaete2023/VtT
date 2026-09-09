# VtT — versión de escritorio V5.1

**Estado de esta guía:** 9 de septiembre de 2026.

VtT transcribe audio y video localmente en Windows, macOS y Linux. La inferencia de Whisper y la identificación de hablantes no envían el audio a una API externa.

## 1. Requisitos e instalación

Requisito mínimo: **Python 3.9 o superior**. El mínimo real viene dado por las versiones actuales de las dependencias del escritorio.

En Windows:

1. Instala Python 3.9+ desde python.org. No se requieren privilegios de administrador si Python puede instalarse para el usuario.
2. Entra en `desktop/`.
3. Ejecuta `run.bat`.

Alternativas: `python run.py`, `py run.py` o, en macOS/Linux, `./run.sh`/`python3 run.py`.

`run.py` crea `desktop/.venv`, instala `requirements.txt` y guarda su SHA-256 en `.venv/.deps_ok`. Si cambian las dependencias o falta un módulo requerido, se reinstalan automáticamente. `python run.py --update` o `--repair` fuerza la actualización.

En Linux pueden hacer falta paquetes del sistema para Tk/PortAudio, según la distribución. En macOS la captura del audio que suena en el sistema requiere un dispositivo virtual, por ejemplo BlackHole. Esos requisitos no afectan la transcripción de archivos existentes.

El entrypoint final es `vtt_main.py`; no ejecutes directamente las capas `vtt_pipeline_*`.

## 2. Flujo recomendado

1. Agrega uno o más archivos, graba desde micrófono/sistema o usa la descarga explícita de YouTube.
2. Elige modelo Whisper e idioma.
3. Selecciona un perfil ASR.
4. Si necesitas voces, activa **Identificar hablantes**, elige Auto o un número de 2 a 8 y selecciona un perfil de diarización.
5. Elige formatos de salida. Word está disponible como `.docx`.
6. Pulsa **Transcribir**.
7. Revisa la salida; si hay hablantes, interpreta el número Auto como una estimación acústica y consulta las métricas de confianza.

## 3. Perfiles ASR

Los perfiles controlan el coste del reconocimiento de voz de forma independiente de la diarización. El código actual puede usar batching también en configuraciones precisas; el documento de salida registra el valor real de `Batch`, `Beam`, backend y perfil utilizado. No deduzcas el backend efectivo solo por el nombre del perfil.

- **Rápido:** prioriza velocidad y menor búsqueda.
- **Equilibrado:** compromiso recomendado para uso habitual.
- **Preciso:** prioriza búsqueda/precisión y puede aumentar el tiempo de proceso.

CPU `int8` es la ruta segura. Si la opción de GPU automática está activa y CTranslate2 detecta CUDA utilizable, VtT puede usar GPU; si el backend no resulta utilizable, la aplicación conserva una ruta CPU.

## 4. Diarización de hablantes

La diarización es una inferencia local separada de Whisper y usa `sherpa-onnx`.

Perfiles:

- **Rápida:** `window_shift_ratio=0.25`, prioriza velocidad.
- **Equilibrada:** `0.20`, recomendada para uso normal.
- **Precisa:** `0.10`, mayor resolución temporal y **alto costo en CPU**.

La primera activación descarga dos modelos desde releases oficiales de k2-fsa:

- segmentación pyannote: ~6,96 MB;
- embedding 3D-Speaker: ~39,59 MB.

Los modelos se almacenan en la carpeta de datos de VtT. Los assets históricos usados no publican un SHA-256 de origen en la metadata consultada: VtT comprueba HTTPS + tamaño en la primera descarga y luego fija un SHA-256 local. Esto detecta alteraciones posteriores, pero no autentica criptográficamente la primera descarga.

### Auto

Auto comienza con un umbral balanceado y analiza estructura de turnos. Si la primera solución presenta señales de subdetección, sobredetección, fragmentación o dominancia anómala, puede hacer una segunda pasada y elegir la solución estructuralmente mejor.

Desde V5.1 el resultado se trata expresamente como **estimación acústica**. El sistema puede marcar:

- estimación estable;
- estimación estable tras reintento;
- estimación con reservas por identidad;
- estimación sospechosa/inestable.

No se presenta Auto como ground truth.

## 5. Alineación palabra ↔ hablante

Cuando la diarización está activa, VtT solicita timestamps por palabra internamente aunque el usuario no quiera exportarlos. Cada palabra se cruza con los turnos acústicos y un segmento Whisper puede dividirse si cambia la voz.

Los timestamps internos pueden quedar ocultos en TXT/DOCX si el usuario no solicitó marcas por palabra; son una herramienta de alineación, no un requisito de presentación.

Existe un fallback por segmento para casos en que no se obtengan palabras temporizadas.

## 6. V5.1 — consistencia de identidad

V5.1 añade una capa conservadora sobre la salida de sherpa:

- calcula embeddings 3D-Speaker de turnos adecuados;
- construye prototipos acústicos por identidad;
- evita usar turnos largos como prototipos, porque pueden contener más de una voz;
- detecta reutilizaciones acústicamente incoherentes de una misma etiqueta;
- solo fusiona una intervención breve con otra identidad cuando existe coincidencia acústica suficiente;
- no elimina una voz únicamente porque dure pocos segundos;
- escanea de forma acotada turnos largos para buscar cambios locales sostenidos;
- limita el escaneo para no convertir la verificación en otra diarización completa;
- si el usuario fija manualmente el número de hablantes, la verificación mide consistencia pero no altera de forma automática ese conteo.

Los umbrales de ingeniería se calibraron con audios oficiales de sherpa-onnx de 2 y 4 hablantes. En esas muestras, pares del mismo hablante llegaron aproximadamente a 0,45 y pares de hablantes diferentes no superaron aproximadamente 0,33. Estas cifras son referencias de calibración, **no umbrales biométricos universales**.

## 7. Worker persistente y rendimiento

La diarización usa un worker persistente durante la sesión. Con el mismo perfil puede reutilizar modelos y motor entre archivos; una segunda pasada Auto puede cambiar clustering mediante `set_config()` sin recargar segmentación/embedding cuando el `window_shift_ratio` no cambia.

El DOCX/JSON registra, según disponibilidad:

- preparación de modelos;
- inicialización/reutilización del motor;
- decodificación para diarización;
- tiempo wall de cada pasada sherpa;
- segmentación/embeddings/clustering internos cuando el backend/SO permite capturarlos;
- tiempo de verificación de identidad y cantidad de embeddings V5.1;
- número de turnos reasignados y cambios locales aplicados.

En Windows los timers internos nativos de sherpa pueden no ser capturables; el tiempo wall por pasada sigue registrándose y es la referencia mínima garantizada.

## 8. Interpretación de la salida Word

El DOCX incluye una tabla de diagnóstico. Entre otros campos puede contener:

- Modelo, idioma y Perfil ASR;
- Backend, Batch y Beam efectivos;
- Hablantes y confianza de la estimación Auto;
- Perfil de diarización y Window shift;
- Pasadas Auto, selección y motivo del reintento;
- duración, carga del modelo, ASR, diarización y procesamiento total;
- alineación de hablantes y segmentos divididos;
- worker persistente/reutilización;
- tiempos sherpa;
- control de identidad V5.1;
- consistencia global y por `Persona N`.

Las etiquetas `alta/media/baja/insuficiente` describen consistencia acústica interna de la agrupación. No identifican personas reales y no constituyen reconocimiento biométrico.

## 9. Exportaciones

- `.txt`: bloques legibles.
- `.md`: bloques/metadata.
- `.docx`: Word estructurado y literal.
- `.json`: fuente maestra **schema v6**.
- `.srt` / `.vtt`: segmentos técnicos sincronizados.

Las exportaciones no sobrescriben silenciosamente una familia existente: se genera un tronco alternativo `nombre (2)`, `nombre (3)`, etc.

El DOCX no corrige semánticamente el ASR. Nombres propios, cifras y frases dudosas siguen requiriendo revisión humana cuando la exactitud sea importante.

## 10. Bloques de lectura y revisión

TXT/Markdown/DOCX agrupan los segmentos en bloques de lectura. SRT/VTT conservan granularidad técnica. Un bloque puede cortarse por cambio de hablante, pausa, fin de oración o límites configurados de duración/caracteres.

La ventana de revisión permite reproducir audio desde un bloque, revisar el texto, renombrar hablantes y exportar una copia revisada sin sobrescribir el original.

## 11. Formatos de entrada

Audio: `.mp3 .wav .m4a .ogg .flac .aac .wma .opus .aif .aiff`.

Video/contenedores: `.mp4 .webm .mkv .avi .mov .m4v .mpeg .mpg .3gp .ts .m2ts`.

Al agregar un archivo, PyAV comprueba que exista una pista de audio. Un contenedor soportado sin audio se rechaza antes de iniciar un trabajo largo.

## 12. Grabación y YouTube

- Micrófono/entrada: `sounddevice`.
- Audio del sistema en Windows: `soundcard`/WASAPI loopback.
- Linux: monitores PulseAudio/PipeWire cuando estén disponibles.
- macOS: para loopback se necesita un dispositivo virtual como BlackHole.

La captura de sistema informa errores al hilo de Tk y conserva un WAV parcial cuando es posible. El hilo escritor es dueño del cierre del WAV para evitar cerrarlo mientras todavía quedan bloques pendientes.

Las grabaciones sin carpeta de salida configurada se guardan en una carpeta persistente; las transcripciones de medios temporales de YouTube se redirigen a una carpeta persistente de transcripciones.

## 13. Privacidad y red

ASR, diarización y verificación de identidad se ejecutan localmente. Internet se usa solamente para:

- instalar/actualizar dependencias;
- primera descarga de modelos Whisper o de diarización;
- descarga explícita mediante YouTube.

VtT no incorpora telemetría ni analytics.

## 14. Verificación automatizada

`Desktop checks` compila los módulos del entrypoint V5.1 y ejecuta `pytest` en Windows, macOS y Ubuntu.

La suite cubre el pipeline histórico y las capas nuevas: agrupación, salidas no destructivas, diarización adaptativa, perfiles, alineación por palabra, worker persistente, timers, validación de conteo, lógica V5.1 de identidad y reportes.

`Desktop executables` construye PyInstaller para los tres sistemas y recopila `faster_whisper`, CTranslate2, onnxruntime, sherpa-onnx, PyAV, Word, sounddevice, soundcard, numpy y CFFI.

Las pruebas de CI no sustituyen una prueba real de micrófono/loopback ni una evaluación humana de voces. Consulta `../PRUEBAS_MANUALES.md`.

## 15. Problemas frecuentes

- **Python no se reconoce:** instala Python 3.9+ para el usuario y vuelve a ejecutar `run.bat`; también puedes probar `py run.py`.
- **Venv/dependencias dañadas:** `python run.py --repair`.
- **Primera transcripción lenta:** puede estar descargando el modelo Whisper.
- **Primera diarización lenta:** descarga los modelos de hablantes y crea el motor.
- **Precisa muy lenta en CPU:** usa `Equilibrada`; `Precisa` está reservada para casos donde la resolución temporal justifique el costo.
- **Auto muestra baja confianza:** revisa las voces o fija manualmente el número si lo conoces.
- **Timers sherpa internos no aparecen en Windows:** usa `Sherpa pasada N (wall)` y el tiempo total de diarización.
- **Un archivo se rechaza:** VtT no encontró una pista de audio decodificable.
- **Captura del sistema no aparece:** verifica el backend del SO; macOS requiere un dispositivo virtual.
