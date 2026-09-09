# VtT — Transcriptor local de voz a texto

VtT transcribe audio y video **en el propio equipo**. La inferencia de voz no envía el audio a una API de transcripción. El repositorio mantiene dos aplicaciones distintas:

- `desktop/`: Python/Tkinter + `faster-whisper` + `sherpa-onnx`, para Windows, macOS y Linux.
- `android/`: Kotlin + `whisper.cpp`, para Android ARM64. Android **no incorpora todavía la diarización V5.1 del escritorio**.

## Escritorio — estado actual V5.1

Requisito: **Python 3.9 o superior**. En Windows, entra en `desktop/` y abre `run.bat`; también puedes ejecutar `python run.py`. El lanzador crea una `.venv`, calcula el SHA-256 de `requirements.txt` y reinstala dependencias cuando ese archivo cambia.

El entrypoint final es `desktop/vtt_main.py`. La arquitectura mantiene `transcriptor_whisper.py` como base histórica y añade capas modulares para pipeline, UI, diarización, alineación, reportes y validación.

Funciones principales:

- modelos Whisper `tiny`, `base`, `small`, `medium` y `large-v3`;
- perfiles ASR **Rápido**, **Equilibrado** y **Preciso**;
- CPU `int8` como ruta segura y CUDA automática solo si CTranslate2 la detecta utilizable;
- VAD, glosario/hotwords y timestamps por palabra opcionales;
- diarización local opcional con `Persona 1`, `Persona 2`, etc.;
- perfiles de diarización **Rápida** (`shift 0.25`), **Equilibrada** (`0.20`, recomendada) y **Precisa** (`0.10`, alto costo CPU);
- número de hablantes Auto o manual entre 2 y 8;
- Auto estructural con una segunda pasada solo cuando el primer resultado es sospechoso;
- worker persistente para reutilizar modelos y motor de diarización entre archivos compatibles;
- alineación palabra↔hablante y división de segmentos cuando cambia la voz;
- V5.1: prototipos acústicos conservadores, control de reutilización de identidad, escaneo acotado de turnos largos y confianza de identidad;
- las intervenciones breves no se fusionan por duración: hace falta evidencia acústica;
- TXT/Markdown/Word en bloques de lectura; SRT/VTT conservan segmentos técnicos;
- exportación `.txt`, `.md`, `.srt`, `.vtt`, `.json` y `.docx`;
- JSON maestro **schema v6** con configuración, métricas, segmentos, bloques, diarización, alineación y diagnóstico de identidad;
- revisión sincronizada con audio y renombrado de hablantes;
- grabación de micrófono y captura de audio del sistema;
- descarga explícita de audio de YouTube;
- procesamiento por lotes, salida no destructiva (`nombre (2)`, etc.) y guardado parcial al cancelar.

La salida Auto se presenta como **estimación acústica**, no como ground truth. V5.1 puede marcar una estimación con reservas o baja confianza cuando la estructura o la consistencia de identidad no son suficientemente estables.

Formatos de entrada oficiales en PC: `.mp3`, `.wav`, `.m4a`, `.ogg`, `.flac`, `.aac`, `.wma`, `.opus`, `.aif`, `.aiff`, `.mp4`, `.webm`, `.mkv`, `.avi`, `.mov`, `.m4v`, `.mpeg`, `.mpg`, `.3gp`, `.ts` y `.m2ts`. VtT valida además que exista una pista de audio decodificable.

### Diarización y modelos

La diarización usa `sherpa-onnx`. La primera activación descarga desde releases oficiales de k2-fsa un modelo de segmentación pyannote (~7 MB) y un modelo 3D-Speaker (~40 MB). Después el procesamiento es local. Los assets históricos usados por VtT no publican un SHA-256 de origen en la metadata consultada; por ello VtT comprueba HTTPS y tamaño en la primera descarga y guarda un SHA-256 local para detectar cambios posteriores. Esto protege integridad local, pero no equivale a autenticación criptográfica de la primera descarga.

Los timestamps por palabra se activan internamente cuando la diarización los necesita, aunque el usuario no solicite mostrarlos en la exportación.

Consulta [`desktop/README.md`](desktop/README.md) para instalación, perfiles, interpretación de métricas, pruebas y solución de problemas.

## Android

La app Android realiza ASR local con `whisper.cpp`, admite audio/video compartido desde otras apps, progreso, cancelación, TXT/SRT y persistencia del último documento. El trabajo vive en `TranscribeViewModel`, por lo que sobrevive a recreaciones de Activity. Los modelos GGML se descargan una vez, se pueden reanudar y quedan protegidos contra corrupción local mediante tamaño y SHA-256 calculados tras la descarga.

Límite actual importante: `AudioDecoder` mantiene el audio decodificado completo en memoria; audios muy largos pueden agotar la RAM. El código captura `OutOfMemoryError` y lo informa, pero la solución estructural por bloques todavía está pendiente.

Consulta [`android/README.md`](android/README.md).

## Estructura principal

```text
desktop/
  transcriptor_whisper.py       base histórica de UI, grabación y utilidades
  vtt_main.py                   entrypoint final
  vtt_core.py                   estructuras, bloques, métricas y exportación base
  vtt_alignment.py              alineación palabra↔hablante
  vtt_diarization_v5.py         worker/motor persistente e instrumentación
  vtt_diarization_v51.py        verificación acústica de identidad
  vtt_identity.py               prototipos, consistencia y escaneo local
  vtt_pipeline_v51.py           pipeline final
  vtt_reporting_v51.py          JSON v6 y DOCX diagnóstico
  tests/                        regresión del escritorio
android/                        Kotlin + whisper.cpp/JNI
.github/workflows/              CI y empaquetado
```

## Privacidad y red

La transcripción y la diarización se procesan localmente. Internet solo se utiliza cuando corresponde para instalar/actualizar dependencias, descargar por primera vez modelos, descargar audio mediante la función explícita de YouTube y construir el proyecto en CI. No se añade telemetría ni analytics.

## Verificación

`Desktop checks` ejecuta `py_compile` y `pytest` en Windows, macOS y Ubuntu. `Desktop executables` construye con PyInstaller en los tres sistemas cuando se ejecuta el workflow manual. `Android APK` construye el APK debug y, si existen los secretos correspondientes, un release firmado opcional.

La CI no sustituye las pruebas con hardware real para micrófono, loopback, velocidad, memoria ni calidad de diarización. Esas pruebas se registran en [`PRUEBAS_MANUALES.md`](PRUEBAS_MANUALES.md).
