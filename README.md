# VtT — Transcriptor local de voz a texto

VtT transcribe audio y video **en el propio equipo**. La inferencia de voz no envía el audio a una API de transcripción. El repositorio mantiene dos aplicaciones relacionadas pero distintas:

- `desktop/`: Python/Tkinter + `faster-whisper` + `sherpa-onnx`, para Windows, macOS y Linux.
- `android/`: Kotlin + `whisper.cpp`, para Android ARM64. Android **no incorpora la diarización del escritorio**.

## Escritorio — estado actual V5.2-performance

Requisito: **Python 3.9 o superior**. En Windows, entra en `desktop/` y abre `run.bat`; también puedes ejecutar `python run.py`. El lanzador crea una `.venv`, calcula el SHA-256 de `requirements.txt` y reinstala dependencias cuando ese archivo cambia.

El entrypoint final es `desktop/vtt_main.py`. `transcriptor_whisper.py` conserva la base histórica y V5.2 añade capas específicas para pipeline, UI, diarización, identidad, alineación, reportes, validación y rendimiento.

Funciones principales:

- modelos Whisper `tiny`, `base`, `small`, `medium` y `large-v3`;
- perfiles ASR **Rápido**, **Equilibrado** y **Preciso**;
- modos globales **Rápido**, **Equilibrado**, **Preciso** y **Personalizado**. Equilibrado usa `small + ASR Equilibrado + diarización Equilibrada` y es la recomendación general; las configuraciones antiguas que no coinciden exactamente con un preset se conservan como Personalizado;
- CPU `int8` como ruta segura y CUDA automática cuando CTranslate2 la detecta utilizable;
- VAD, glosario/hotwords y timestamps por palabra opcionales;
- diarización local con perfiles **Rápida** (`shift 0.25`), **Equilibrada** (`0.20`) y **Precisa** (`0.10`);
- número de hablantes Auto o manual entre 2 y 8;
- Auto V5.2 con análisis estructural, precheck acústico acotado y selección identity-aware: puede evitar una segunda pasada completa si la evidencia barata resuelve una sobredetección;
- reutilización de modelos, motor, PCM y embeddings dentro del trabajo/sesión cuando es seguro;
- sonda barata de tres ventanas antes del escaneo detallado de turnos largos;
- alineación palabra↔hablante y división de segmentos cuando cambia la voz;
- conteos separados de clusters sherpa, clusters tras control de identidad y hablantes que recibieron texto;
- TXT/Markdown/Word en bloques de lectura; SRT/VTT conservan segmentos técnicos;
- exportación `.txt`, `.md`, `.srt`, `.vtt`, `.json` y `.docx`;
- JSON maestro **schema v7** con configuración, métricas, rendimiento, diarización, identidad, alineación y trazabilidad de Auto;
- revisión sincronizada con audio y renombrado de hablantes;
- grabación de micrófono y captura de audio del sistema;
- descarga explícita de audio de YouTube;
- procesamiento por lotes y salidas no destructivas (`nombre (2)`, etc.).

La salida Auto es una **estimación acústica**, no ground truth. La capa V5.2 puede marcar resultados estables, con reservas o ambiguos y deja en JSON/Word la evidencia utilizada.

Formatos de entrada oficiales en PC: `.mp3`, `.wav`, `.m4a`, `.ogg`, `.flac`, `.aac`, `.wma`, `.opus`, `.aif`, `.aiff`, `.mp4`, `.webm`, `.mkv`, `.avi`, `.mov`, `.m4v`, `.mpeg`, `.mpg`, `.3gp`, `.ts` y `.m2ts`. Se valida que exista una pista de audio decodificable.

### Diarización y modelos

La diarización usa `sherpa-onnx`. La primera activación descarga desde releases oficiales de k2-fsa un modelo pyannote (~7 MB) y un embedding 3D-Speaker (~40 MB). Los assets históricos no publican `digest` en la metadata de GitHub, por lo que VtT mantiene **hashes SHA-256 auditados y fijados** tras dos descargas independientes de los assets oficiales el 9 de septiembre de 2026. Se comprueba el archive de segmentación, el ONNX extraído y el embedding antes de usarlos. Estos pins eliminan el TOFU anterior de VtT, aunque no deben describirse como una firma publicada por upstream.

Los timestamps por palabra se activan internamente cuando la diarización los necesita, aunque el usuario no solicite mostrarlos.

Consulta [`desktop/README.md`](desktop/README.md) para instalación, perfiles, métricas y solución de problemas.

## Android

La app Android realiza ASR local con `whisper.cpp`, admite audio/video compartido desde otras apps, progreso, cancelación, TXT/SRT y persistencia del último documento.

Desde la revisión de septiembre de 2026:

- los GGML `tiny`, `base` y `small` se comparan contra SHA-256 esperados antes de promover una primera descarga a modelo válido;
- las descargas siguen siendo reanudables mediante `Range`;
- audios de más de 5 minutos se procesan en ventanas de 90 s con 2 s de solapamiento para acotar la memoria; timestamps y palabras se desplazan al tiempo global y se deduplica el solape;
- el puente JNI usa identificadores opacos y `shared_ptr`/mutex para liberar también el pequeño Handle sin la fuga deliberada anterior;
- whisper.cpp sigue fijado a un commit exacto.

Android continúa **sin diarización de hablantes**. La calidad de bloques largos, memoria, batería y temperatura requieren validación en dispositivo físico.

Consulta [`android/README.md`](android/README.md).

## Estructura principal

```text
desktop/
  transcriptor_whisper.py       base histórica de UI, grabación y utilidades
  vtt_main.py                   entrypoint final V5.2
  vtt_core.py                   estructuras, bloques y exportación base
  vtt_alignment.py              alineación palabra↔hablante
  vtt_diarization_v5.py         motor base persistente e instrumentación
  vtt_identity_v52.py           identidad rival-aware y sonda de turnos largos
  vtt_diarization_v52.py        Auto V5.2 / precheck / selección identity-aware
  vtt_pipeline_v52.py           pipeline final
  vtt_reporting_v52.py          JSON v7 y DOCX diagnóstico
  vtt_validation_v52.py         validación y conteos por etapa
  vtt_performance.py            modos globales y presupuesto de rendimiento
  tests/                        regresión del escritorio
android/                        Kotlin + whisper.cpp/JNI
.github/workflows/              CI y empaquetado
```

## Privacidad y red

La transcripción y la diarización se procesan localmente. Internet solo se utiliza cuando corresponde para instalar/actualizar dependencias, descargar por primera vez modelos, descargar audio mediante la función explícita de YouTube y ejecutar CI/build. No se añade telemetría ni analytics.

## Verificación

`Desktop checks` ejecuta `py_compile` y `pytest` en Windows, macOS y Ubuntu. `Desktop executables` construye con PyInstaller en los tres sistemas. `Android APK` construye el APK debug y, si existen los secretos correspondientes, un release firmado opcional. Las Actions relevantes están fijadas por SHA.

La campaña acústica V5.2 con audios oficiales de sherpa de 2 y 4 hablantes reprodujo correctamente ambos conteos y comprobó reutilización del worker. El benchmark ASR público es solo una prueba de rendimiento del pipeline; no sustituye una evaluación del audio real del usuario.

La CI no sustituye las pruebas con hardware real para micrófono, loopback, velocidad en un PC específico, memoria/batería Android ni calidad acústica en material no anotado. Esas pruebas se registran en [`PRUEBAS_MANUALES.md`](PRUEBAS_MANUALES.md).
