# VtT — Transcriptor local de voz a texto

VtT transcribe audio y video **en tu propio equipo**. El audio no se envía a servicios de transcripción en la nube. En PC usa `faster-whisper`/CTranslate2; en Android usa `whisper.cpp`.

## PC — Windows, macOS y Linux

Requisito: **Python 3.9 o superior**. En Windows, la forma normal de abrirlo es `desktop/run.bat`; también puedes ejecutar `python desktop/run.py`. El lanzador crea un entorno `.venv`, instala o actualiza las dependencias cuando cambia `requirements.txt` y abre la aplicación mejorada.

Funciones principales del escritorio:

- perfiles **Rápido**, **Equilibrado** y **Preciso**;
- batching con `faster-whisper` en los perfiles Rápido/Equilibrado;
- CPU `int8` como ruta segura y GPU CUDA solo si el equipo ya dispone de un entorno compatible; si falla, vuelve a CPU;
- filtro VAD y marcas por palabra opcionales;
- glosario/hotwords para nombres propios y términos frecuentes;
- diarización local opcional: `Persona 1`, `Persona 2`, etc.;
- bloques de lectura de mayor tamaño para TXT/Markdown/Word, manteniendo los segmentos finos para SRT/VTT;
- exportación `.txt`, `.md`, `.srt`, `.vtt`, `.json` y **`.docx`**;
- JSON maestro v2 con segmentos, bloques de lectura, hablantes, métricas y marcas de revisión;
- marcas de baja confianza para orientar la revisión humana, sin eliminar texto;
- ventana de revisión: reproducir audio desde un bloque, renombrar hablantes y exportar una versión revisada sin sobrescribir el original;
- grabación desde micrófono y captura de audio del sistema;
- descarga de audio de YouTube;
- procesamiento por lotes y guardado parcial al cancelar.

Formatos admitidos oficialmente en PC: `.mp3`, `.wav`, `.m4a`, `.ogg`, `.flac`, `.aac`, `.wma`, `.opus`, `.aif`, `.aiff`, `.mp4`, `.webm`, `.mkv`, `.avi`, `.mov`, `.m4v`, `.mpeg`, `.mpg`, `.3gp`, `.ts` y `.m2ts`. Además de la extensión, VtT comprueba que el archivo contenga una pista de audio decodificable.

La diarización usa `sherpa-onnx`. La primera vez que se activa descarga dos modelos oficiales (~7 MB y ~40 MB); después funciona offline. Los assets históricos de GitHub no publican un SHA-256 de origen, por lo que VtT verifica origen HTTPS y tamaño en la primera descarga y guarda un SHA-256 local para detectar alteraciones posteriores. Esta limitación está documentada deliberadamente: no se inventan hashes de confianza.

Consulta [`desktop/README.md`](desktop/README.md) para instalación, uso y solución de problemas.

## Android

La app Android nativa usa `whisper.cpp` y mantiene la inferencia local. Consulta [`android/README.md`](android/README.md) para instalación y funcionamiento. Las mejoras de presentación del escritorio se implementan primero y se validan antes de trasladar componentes pesados de diarización al APK.

## Estructura

```text
desktop/
  transcriptor_whisper.py   base estable: UI, grabación, YouTube y utilidades
  vtt_core.py               agrupación, métricas, JSON v2 y exportaciones
  vtt_diarization.py        diarización offline y gestión de modelos
  vtt_enhanced.py           aplicación VtT mejorada
  run.py                    lanzador/autoinstalador
  tests/                    pruebas del pipeline y de las mejoras
android/                    app Kotlin + whisper.cpp
.github/workflows/          CI y builds
```

## Privacidad

La inferencia de voz y la diarización se realizan localmente. Solo se necesita Internet para instalar/actualizar dependencias, descargar por primera vez los modelos seleccionados y usar la función explícita de descarga desde YouTube.

## Créditos

- OpenAI Whisper
- SYSTRAN `faster-whisper`
- CTranslate2
- `sherpa-onnx` / k2-fsa para diarización local
- `python-docx` para exportación Word
- `yt-dlp`
- `whisper.cpp` en Android
