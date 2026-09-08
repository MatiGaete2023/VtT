# VtT — versión de escritorio

**Fecha de esta guía:** 8 de septiembre de 2026.

VtT transcribe audio y video localmente en Windows, macOS y Linux. La inferencia no envía el audio a una API externa.

## 1. Requisitos e instalación

Necesitas **Python 3.9 o superior**. Esta versión eleva el mínimo anterior de 3.8 porque `faster-whisper` actual requiere Python >=3.9.

En Windows:

1. Instala Python desde python.org y marca `Add Python to PATH` si el instalador lo ofrece.
2. Entra a `desktop/`.
3. Haz doble clic en `run.bat`.

Alternativamente: `python run.py` (o `py run.py` en Windows).

El lanzador crea `desktop/.venv`, instala las dependencias y recuerda un SHA-256 de `requirements.txt`. Si las dependencias cambian, se actualizan automáticamente. `python run.py --update` fuerza la reinstalación.

## 2. Flujo recomendado

1. Agrega uno o más archivos, graba desde micrófono/sistema o descarga el audio de YouTube.
2. Elige el modelo Whisper y el idioma.
3. En `VtT > Opciones avanzadas…` elige perfil, Word, hablantes, glosario y tamaño de bloques.
4. Pulsa **Transcribir**.
5. Abre la carpeta de salida o `VtT > Revisar última transcripción…`.

## 3. Perfiles de velocidad

- **Rápido:** batching `8` y `beam_size=1`. Prioriza velocidad.
- **Equilibrado:** batching `8` y `beam_size=5`. Es el perfil recomendado.
- **Preciso:** ruta secuencial y `beam_size=5`. Útil para comparar audios difíciles.

VtT usa CPU `int8` como ruta segura. Si `Usar GPU compatible automáticamente` está activo y CTranslate2 detecta CUDA utilizable, intenta GPU `float16`; ante error vuelve a CPU sin convertir CUDA en requisito.

Cada trabajo registra duración, tiempo de procesamiento, **RTF** (`tiempo_proceso / duración_audio`) y velocidad aproximada `x tiempo real`. Esos datos permiten comparar perfiles en el mismo PC.

## 4. Hablantes / diarización

Activa `Identificar hablantes` para obtener `Persona 1`, `Persona 2`, etc. Puedes dejar el número en **Auto** o indicar entre 2 y 8 hablantes.

La diarización es una segunda inferencia local con `sherpa-onnx`, separada de Whisper. La primera vez descarga desde releases oficiales de k2-fsa:

- segmentación pyannote: ~6,96 MB;
- embedding 3D-Speaker ERes2Net: ~39,59 MB.

Los assets históricos no ofrecen un digest SHA-256 de origen en la metadata de GitHub. VtT no inventa uno: comprueba HTTPS + tamaño exacto al descargar y guarda un SHA-256 local; en ejecuciones posteriores rechaza modificaciones respecto de ese pin local. Los modelos se guardan en la carpeta de datos de VtT y no se vuelven a descargar si están íntegros.

La diarización puede fallar con voces superpuestas, interrupciones rápidas, ruido o audio lejano. Por eso los nombres son etiquetas de trabajo y se pueden renombrar en la revisión.

## 5. Segmentos técnicos vs. bloques de lectura

Whisper sigue produciendo segmentos cortos. VtT **no los destruye**:

- SRT/VTT conservan los segmentos finos para sincronización;
- JSON conserva los segmentos y sus métricas;
- TXT/Markdown/DOCX agrupan esos segmentos en bloques legibles.

Un bloque se corta por cambio de hablante, pausa relevante, fin de oración cuando ya tiene suficiente extensión o límites de tiempo/caracteres. Los valores de pausa y duración máxima pueden modificarse en Opciones avanzadas.

## 6. Word y demás exportaciones

Formatos disponibles:

- `.txt`: bloques de lectura;
- `.md`: bloques de lectura con metadata;
- `.docx`: documento Word estructurado y literal;
- `.json`: fuente maestra v2;
- `.srt` y `.vtt`: subtítulos con segmentos técnicos.

El DOCX no “mejora” ni reescribe semánticamente lo dicho. Solo estructura el texto ASR, timestamps y hablantes. La revisión humana sigue siendo necesaria cuando el uso exige exactitud.

## 7. Glosario / hotwords

En `Glosario / nombres importantes` escribe términos separados por coma o punto y coma. VtT elimina duplicados y los entrega a Whisper como `hotwords`. Es útil para nombres propios, instituciones, siglas y vocabulario recurrente.

## 8. Fragmentos para revisar

El JSON v2 conserva `avg_logprob`, `no_speech_prob` y `compression_ratio` cuando el motor los entrega. VtT usa umbrales conservadores para **marcar** bloques dudosos; nunca elimina ni corrige silenciosamente una frase basándose en esas métricas.

En la ventana de revisión puedes:

- ver los bloques en orden temporal;
- reproducir unos segundos desde el timestamp seleccionado;
- renombrar un hablante en toda la transcripción;
- exportar una revisión nueva sin sobrescribir el original.

## 9. Formatos de entrada oficiales

Audio: `.mp3 .wav .m4a .ogg .flac .aac .wma .opus .aif .aiff`.

Video/contenedores: `.mp4 .webm .mkv .avi .mov .m4v .mpeg .mpg .3gp .ts .m2ts`.

La extensión ya no basta: al agregar un archivo, VtT intenta abrirlo con PyAV y confirma que exista una pista de audio. Un contenedor soportado sin audio se rechaza antes de iniciar un trabajo largo.

## 10. Grabación y audio del sistema

Se conservan las funciones de la versión base:

- micrófono/entrada mediante `sounddevice`;
- audio del sistema en Windows mediante `soundcard`/WASAPI loopback;
- monitores PulseAudio/PipeWire en Linux;
- macOS requiere un dispositivo virtual como BlackHole para capturar lo que suena en el sistema.

Las grabaciones se guardan en una carpeta persistente. Los temporales de YouTube no son el destino de la transcripción final.

## 11. Carpetas y privacidad

Los datos persistentes se guardan junto a la app cuando la carpeta es escribible; en ejecutables ubicados en carpetas protegidas se usa la carpeta de datos del usuario. Modelos, grabaciones y transcripciones no se versionan en Git.

Internet se usa solo para: instalación/actualización de dependencias, primera descarga de modelos y descarga explícita desde YouTube. La inferencia de transcripción/diarización es local.

## 12. Verificación

La CI compila `transcriptor_whisper.py`, `vtt_core.py`, `vtt_diarization.py`, `vtt_enhanced.py` y `run.py`, y ejecuta `pytest` en Windows, macOS y Linux.

Las pruebas automatizadas cubren, entre otros puntos:

- tubería de grabación;
- persistencia y exportación segura;
- agrupación de segmentos;
- cortes por hablante/pausa;
- asignación temporal de hablantes;
- métricas RTF;
- JSON v2;
- SRT con hablantes;
- DOCX generado y reabierto;
- pin SHA-256 local de modelos de diarización.

Además debe realizarse una prueba manual en hardware real para medir velocidad, RAM, calidad de diarización y reproducción de revisión. Esa evidencia no puede reemplazarse por CI.

## 13. Ejecutable independiente

`.github/workflows/desktop-build.yml` construye ejecutables con PyInstaller para Windows, macOS y Linux e incluye las dependencias de Whisper, Word, diarización, audio y PyAV. La build no descarga los modelos de voz ni de hablantes: se obtienen cuando el usuario elige usarlos.

## 14. Problemas frecuentes

- **Python no se reconoce:** reinstala Python y habilita PATH o usa `py run.py` en Windows.
- **Dependencia incompleta:** ejecuta `python run.py --update`.
- **Primera transcripción lenta:** puede estar descargando el modelo Whisper.
- **Primera diarización lenta:** descarga una vez los dos modelos de hablantes.
- **GPU detectada pero falla:** VtT vuelve a CPU `int8`; no necesitas CUDA para usar la app.
- **Un archivo se rechaza:** VtT no detectó una pista de audio decodificable; conviértelo a WAV/M4A/MP3 o a un contenedor soportado.
- **Hablantes incorrectos:** prueba indicando el número real de participantes y revisa el resultado; superposición y ruido afectan la diarización.
