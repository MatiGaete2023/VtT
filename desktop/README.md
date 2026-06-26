# Transcriptor Whisper — versión de escritorio (Windows · macOS · Linux)

Transcribe audio y video a texto **en tu propio equipo**, sin enviar nada a internet
(salvo la descarga inicial del programa y del modelo). Funciona igual en Windows,
macOS y Linux, **sin permisos de administrador**.

## Lo único que necesitas

**Python 3.8 o superior** instalado.

- **Windows / macOS:** descárgalo de <https://www.python.org/downloads/>.
  En Windows, marca la casilla **"Add Python to PATH"** durante la instalación.
- **Linux (Debian/Ubuntu):** `sudo apt install python3 python3-venv python3-tk`

> El propio Python ya incluye la interfaz gráfica (Tkinter). En Linux, el paquete
> `python3-tk` la habilita; en macOS usa el instalador oficial de python.org para
> que Tkinter venga incluido.

## Cómo usarlo (instala solo lo necesario, la primera vez)

1. Descarga esta carpeta `desktop/` en tu equipo.
2. Ábrela y ejecuta:
   - **Windows:** doble clic en **`run.bat`**
   - **macOS / Linux:** doble clic en **`run.sh`** (o en una terminal: `./run.sh`)
   - **Cualquier sistema:** `python run.py`

La primera vez, el lanzador:

1. Crea un entorno aislado (`.venv`) dentro de la carpeta.
2. Descarga **solo** las dependencias necesarias (`faster-whisper`, `yt-dlp`).
3. Abre la aplicación.

La **primera transcripción** descarga una vez el modelo de voz elegido y lo guarda
en tu equipo. A partir de ahí funciona **sin conexión**.

> Las siguientes veces ya no se descarga nada: el programa abre directo.
> Para actualizar las dependencias en el futuro: `python run.py --update`.

## ¿Qué hace?

- Transcribe `.mp3 .wav .m4a .ogg .flac .mp4 .aac .wma .opus .webm .mkv .avi`.
- Descarga audio de YouTube (pega la URL) para transcribirlo.
- Modelos: `tiny`, `base`, `small`, `medium`, `large-v3` (más grande = más preciso y más lento).
- Idiomas: español, inglés, portugués, francés o detección automática.
- Exporta a `.txt`, `.md` (Obsidian), `.srt` y `.vtt`.
- No necesita FFmpeg para transcribir (lo decodifica internamente). FFmpeg solo
  mejora, opcionalmente, las descargas de YouTube.

## Llevarlo a otro equipo sin descargar de nuevo

Como todo vive dentro de la carpeta, puedes copiarla completa (incluida `.venv` y la
caché del modelo) a otro PC del **mismo sistema operativo** y funcionará sin internet.
Para distinto sistema operativo, copia la carpeta **sin** `.venv` y vuelve a ejecutar
`run.py` allí (recreará el entorno para esa plataforma).

## ¿Prefieres un ejecutable sin instalar Python?

Hay un flujo de GitHub Actions (`.github/workflows/desktop-build.yml`) que genera
ejecutables independientes para Windows, macOS y Linux con PyInstaller. Ejecútalo
desde la pestaña **Actions** del repositorio y descarga el artefacto de tu sistema.

## Problemas frecuentes

| Síntoma | Solución |
|---|---|
| "Python no se reconoce" (Windows) | Reinstala Python marcando **Add Python to PATH**. |
| Error al crear `.venv` (Linux) | `sudo apt install python3-venv python3-tk` |
| No abre la ventana (Linux) | Falta Tkinter: `sudo apt install python3-tk` |
| La primera transcripción tarda | Está descargando el modelo una sola vez; luego es rápido. |
