# VtT — Transcriptor local de voz a texto

VtT transcribe audio y video **en el propio equipo**. La inferencia de voz no envía el audio a una API de transcripción. El repositorio mantiene dos aplicaciones relacionadas pero distintas:

- `desktop/`: Python/Tkinter + `faster-whisper` + `sherpa-onnx`, para Windows, macOS y Linux.
- `android/`: Kotlin + `whisper.cpp`, para Android ARM64. Android **no incorpora la diarización del escritorio**.

## Estado actual

La rama de trabajo `claude/voice-transcriber-multiplatform-6xifq1` contiene **V5.2.1-performance/integration**. V5.2.1 conserva la arquitectura acústica V5.2 y corrige integración, métricas, recuperación ante cancelación, semántica de presets y costo de exportación. La calidad acústica exacta sobre audios reales no anotados, DER/JER, CUDA y pruebas de hardware siguen siendo validaciones externas y no se presentan como resueltas.

## Escritorio — V5.2.1

Requisito: **Python 3.9 o superior**. En Windows, entra en `desktop/` y abre `run.bat`; también puedes ejecutar `python run.py`. El lanzador crea una `.venv`, calcula el SHA-256 de `requirements.txt` y reinstala dependencias cuando ese archivo cambia.

El entrypoint final es `desktop/vtt_main.py`. `transcriptor_whisper.py` conserva la base histórica y V5.2.1 añade capas específicas para pipeline, UI, diarización, identidad, alineación, reportes, validación, métricas y rendimiento.

Funciones principales:

- modelos Whisper `tiny`, `base`, `small`, `medium` y `large-v3`;
- perfiles ASR **Rápido**, **Equilibrado** y **Preciso**;
- modos globales completos **Rápido**, **Equilibrado**, **Preciso** y **Personalizado**. Los tres presets activan identificación de hablantes en **Auto**; Personalizado deja libres todos los controles;
- **Equilibrado** usa `small + ASR Equilibrado + hablantes Auto + diarización Equilibrada (shift 0.20)` y es la recomendación general;
- **Preciso** usa `medium + ASR Preciso + hablantes Auto + diarización Equilibrada (shift 0.20)`. La diarización **Precisa 0.10** permanece disponible como opción avanzada en Personalizado, porque su costo en CPU institucional resultó incompatible con uso habitual;
- CPU `int8` como ruta segura y CUDA automática cuando CTranslate2 la detecta utilizable;
- VAD, glosario/hotwords y timestamps por palabra opcionales;
- diarización local con perfiles **Rápida** (`shift 0.25`), **Equilibrada** (`0.20`) y **Precisa** (`0.10`);
- número de hablantes Auto o manual entre 2 y 8;
- Auto V5.2 con análisis estructural, precheck acústico acotado y selección identity-aware;
- **presupuesto temporal Auto por preset**: tras la primera pasada se proyecta el costo de repetir Sherpa; si una segunda pasada haría inviable el objetivo temporal del preset, se conserva la mejor primera solución y se marca explícitamente como ambigua por presupuesto;
- reutilización de modelos, motor, PCM y embeddings dentro del trabajo/sesión cuando es seguro;
- sonda barata de tres ventanas antes del escaneo detallado de turnos largos;
- alineación palabra↔hablante y división de segmentos cuando cambia la voz;
- conteos separados y trazables de **clusters Sherpa**, **identidades acústicas auditadas**, **hablantes con texto** e **identidades sin texto**; nunca se sustituye el conteo acústico por `len(speakers)`;
- cancelación unificada entre servicios V5/V5.1/V5.2;
- checkpoint `*_ASR_RECUPERABLE.json` después del reconocimiento y antes de una diarización costosa; se elimina al completar correctamente y se conserva si la diarización falla o se cancela;
- métricas separadas de `processing_seconds`, `report_generation_seconds` y `end_to_end_seconds`;
- estado de rendimiento recalculado desde tiempos finales, no desde una copia previa a la exportación;
- DOCX V5.2 construido directamente y guardado **una sola vez** por salida final, en vez de encadenar escritores V4→V5→V5.1→V5.2;
- TXT/Markdown/Word en bloques de lectura; SRT/VTT conservan segmentos técnicos;
- exportación `.txt`, `.md`, `.srt`, `.vtt`, `.json` y `.docx`;
- JSON maestro **schema v8** con configuración, tiempos finales, rendimiento, diarización, identidad, alineación, presupuesto y trazabilidad de Auto;
- revisión sincronizada con audio y renombrado de hablantes;
- grabación de micrófono y captura de audio del sistema;
- descarga explícita de audio de YouTube;
- procesamiento por lotes y salidas no destructivas (`nombre (2)`, etc.).

La salida Auto es una **estimación acústica**, no ground truth. La capa V5.2 puede marcar resultados estables, con reservas, ambiguos o limitados por presupuesto y deja en JSON/Word la evidencia utilizada.

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
- el puente JNI usa identificadores opacos y `shared_ptr`/mutex para liberar también el Handle sin la fuga deliberada anterior;
- whisper.cpp sigue fijado a un commit exacto.

Android continúa **sin diarización de hablantes**. La calidad de bloques largos, memoria, batería y temperatura requieren validación en dispositivo físico.

Consulta [`android/README.md`](android/README.md).

## Estructura principal

```text
desktop/
  transcriptor_whisper.py          base histórica de UI, grabación y utilidades
  vtt_main.py                      entrypoint final V5.2
  vtt_core.py                      estructuras, bloques y exportación base
  vtt_alignment.py                 alineación palabra↔hablante
  vtt_diarization_errors.py        excepción de cancelación compartida
  vtt_diarization_v5.py            motor base persistente e instrumentación
  vtt_identity_v52.py              identidad rival-aware y sonda de turnos largos
  vtt_diarization_v52.py           Auto V5.2 / precheck / presupuesto / selección
  vtt_diarization_v52_metrics.py   contabilidad completa del trabajo de identidad
  vtt_diarization_service_v52.py   worker persistente final
  vtt_pipeline_v52.py              pipeline final y conteos por etapa
  vtt_reporting_v52.py             JSON v8 y DOCX diagnóstico de un solo guardado
  vtt_validation_v52.py            validación de conteos por etapa
  vtt_performance.py               presets completos y presupuesto de rendimiento
  tests/                           regresión del escritorio
android/                           Kotlin + whisper.cpp/JNI
.github/workflows/                 CI y empaquetado
```

Los módulos `v4`, `v5` y `v51` que aún existen forman la cadena de compatibilidad/herencia del pipeline final; no deben interpretarse como entrypoints alternativos ni eliminarse solo por su nombre de versión.

## Mapa de documentación

- [`desktop/README.md`](desktop/README.md): instalación, perfiles, pipeline y diagnóstico de escritorio.
- [`android/README.md`](android/README.md): instalación, modelos, bloques largos y JNI Android.
- [`MODEL_CATALOG.md`](MODEL_CATALOG.md): fuentes, tamaños, hashes y política de actualización de modelos.
- [`AUDITORIA.md`](AUDITORIA.md): hallazgos corregidos, evidencia CI/build y límites vigentes.
- [`PLAN_MAESTRO.md`](PLAN_MAESTRO.md): arquitectura, fases cerradas y próximas validaciones externas.
- [`PRUEBAS_MANUALES.md`](PRUEBAS_MANUALES.md): pruebas que CI no puede sustituir.
- [`AGENTS.md`](AGENTS.md): contrato para futuras modificaciones del repositorio.
- [`android/RELEASE_SETUP.md`](android/RELEASE_SETUP.md): configuración externa necesaria para un APK de producción firmado.

## Privacidad y red

La transcripción y la diarización se procesan localmente. Internet solo se utiliza cuando corresponde para instalar/actualizar dependencias, descargar por primera vez modelos, descargar audio mediante la función explícita de YouTube y ejecutar CI/build. No se añade telemetría ni analytics.

## Verificación

`Desktop checks` ejecuta `py_compile` y `pytest` en Windows, macOS y Ubuntu. `Desktop executables` construye con PyInstaller en los tres sistemas. `Android APK` construye el APK debug y, si existen los secretos correspondientes, un release firmado opcional. Las Actions relevantes están fijadas por SHA.

La campaña acústica V5.2 con audios oficiales de sherpa de 2 y 4 hablantes reprodujo correctamente ambos conteos y comprobó reutilización del worker. El benchmark ASR público es solo una prueba de rendimiento del pipeline; no sustituye una evaluación del audio real del usuario.

La prueba institucional del 12 de septiembre mostró además que `small + ASR Equilibrado` sin diarización procesó 6:44 de audio en ~2:44. Esa ejecución reveló un defecto de semántica de la UI —el antiguo preset global no activaba hablantes— que V5.2.1 corrige. La próxima comparación válida debe ejecutarse con **Equilibrado + Auto realmente activo**.

La CI no sustituye las pruebas con hardware real para micrófono, loopback, velocidad en un PC específico, memoria/batería Android ni calidad acústica en material no anotado. Esas pruebas se registran en [`PRUEBAS_MANUALES.md`](PRUEBAS_MANUALES.md).