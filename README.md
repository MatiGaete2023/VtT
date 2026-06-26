# VtT — Transcriptor de voz a texto (multiplataforma)

Transcribe audio y video a texto **en tu propio equipo**, sin servicios en la nube.
El motor es [Whisper](https://github.com/openai/whisper) (de OpenAI), ejecutado
localmente. Pensado para **instalarse y funcionar en cualquier equipo con la menor
configuración posible**: solo descarga lo que necesita para funcionar.

| Plataforma | Cómo se instala | Dónde |
|---|---|---|
| **Windows · macOS · Linux** | Doble clic en `run.bat` / `run.sh` (o `python run.py`). Se auto-instala la 1ª vez. | [`desktop/`](desktop/) |
| **Android** | Descargas e instalas un APK (lo construye GitHub Actions). 100 % offline. | [`android/`](android/) |

## Idea general

- **No requiere configuración compleja.** En PC solo necesitas Python; en Android,
  solo instalar el APK.
- **Descarga solo lo necesario.** Las dependencias y el modelo de voz se bajan una
  única vez la primera vez; después funciona sin conexión.
- **Privado.** El audio nunca sale de tu equipo: la transcripción es local.

## Empezar rápido

### En computador (Windows / macOS / Linux)

1. Instala **Python 3.8+** (en Windows marca *"Add Python to PATH"*).
2. Entra a la carpeta [`desktop/`](desktop/) y ejecuta:
   - Windows: doble clic en **`run.bat`**
   - macOS / Linux: **`./run.sh`**
   - Cualquiera: **`python run.py`**

La primera vez crea su entorno, instala lo necesario y abre la app.
Detalles y solución de problemas: [`desktop/README.md`](desktop/README.md).

### En Android

1. En **Actions → "Android APK"**, descarga el artefacto `TranscriptorVtT-debug-apk`
   (o el APK de la *release* `android-latest`).
2. Instálalo en el teléfono (acepta "orígenes desconocidos").
3. Elige modelo e idioma, selecciona un audio y toca **Transcribir**.

Detalles: [`android/README.md`](android/README.md).

## Estructura del repositorio

```
desktop/                 App de escritorio (Tkinter + faster-whisper) y auto-instalador
  transcriptor_whisper.py  La aplicación (multiplataforma)
  run.py                   Lanzador que auto-instala dependencias en un entorno local
  requirements.txt         Dependencias (faster-whisper, yt-dlp)
  run.bat / run.sh         Accesos directos para Windows / macOS / Linux
android/                 App Android nativa (Kotlin + whisper.cpp vía JNI)
  app/src/main/cpp/        Puente JNI y CMake (descarga whisper.cpp al compilar)
  app/src/main/java/…      UI y lógica (descarga de modelo, decodificación, transcripción)
.github/workflows/
  android-build.yml        Construye el APK automáticamente y lo publica como artefacto
  desktop-build.yml        (Opcional) genera ejecutables independientes para PC
```

## Funciones

- Modelos Whisper: `tiny`, `base`, `small` (y en PC también `medium`, `large-v3`).
- Idiomas: español, inglés, portugués, francés y detección automática.
- PC: graba desde el micrófono/entrada, exporta `.txt` (con líneas ajustadas para leer
  sin scroll horizontal), `.md`, `.srt`, `.vtt`; además descarga audio de YouTube.
- Android: transcribe archivos del teléfono y permite copiar/compartir el texto.

## Créditos

- [openai/whisper](https://github.com/openai/whisper) — modelo de transcripción.
- [SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper) — motor en PC (CTranslate2).
- [ggerganov/whisper.cpp](https://github.com/ggerganov/whisper.cpp) — motor en Android.
- [yt-dlp/yt-dlp](https://github.com/yt-dlp/yt-dlp) — descarga de audio de YouTube.
