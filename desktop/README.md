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
2. Descarga **solo** las dependencias necesarias (ver `requirements.txt`).
3. Abre la aplicación.

La **primera transcripción** descarga una vez el modelo de voz elegido y lo guarda
en tu equipo. A partir de ahí funciona **sin conexión**.

> Las siguientes veces ya no se descarga nada: el programa abre directo. **Si se agrega
> una dependencia nueva** (por ejemplo al actualizar la app), el lanzador lo detecta
> solo comparando `requirements.txt` y la instala automáticamente — no necesitas hacer
> nada manual. `python run.py --update` fuerza la reinstalación completa igualmente.

## ¿Qué hace?

- Transcribe `.mp3 .wav .m4a .ogg .flac .mp4 .aac .wma .opus .webm .mkv .avi`.
- **Graba desde el micrófono / entrada de audio** y agrega la grabación para transcribir.
- Descarga audio de YouTube (pega la URL) para transcribirlo, con **barra de progreso**
  de la descarga.
- **Modo claro / oscuro**: botón 🌙/☀️ arriba a la derecha; se recuerda entre sesiones.
- Modelos: `tiny`, `base`, `small`, `medium`, `large-v3` (más grande = más preciso y más lento).
- Idiomas: español, inglés, portugués, francés o detección automática.
- Exporta a `.txt`, `.md` (Obsidian), `.srt`, `.vtt` y `.json` estructurado. El
  `.txt` viene **ajustado a ~100 caracteres por línea**, para leerlo sin desplazarte
  hacia el lado. El JSON conserva segmentos, marcas por palabra disponibles y un
  campo preparado para hablante; activa la opción `.json (tiempos)` para generarlo.
- Conserva puntos internos del nombre (`audiencia.01`) y crea una copia numerada
  si la salida ya existe; no sobrescribe una transcripción anterior.
- Si cancelas después de obtener segmentos, guarda una salida parcial. En un lote,
  un archivo defectuoso se registra y el programa continúa con los siguientes.
- Mientras transcribe, el **Registro** muestra cada segmento a medida que sale y el
  estado indica un **tiempo restante estimado**.
- No necesita FFmpeg para transcribir (lo decodifica internamente). FFmpeg solo
  mejora, opcionalmente, las descargas de YouTube.
- **Arrastra y suelta** archivos de audio/video directo sobre la lista (necesita
  el paquete opcional `tkinterdnd2`, ver abajo).
- Atajos de teclado: **Ctrl+O** agrega archivos, **Ctrl+R** graba/detiene,
  **Ctrl+Enter** transcribe (en macOS también funcionan con ⌘).
- **Historial** (botón junto a "Abrir carpeta de salida"): accede rápido a las
  últimas 10 carpetas donde se guardaron transcripciones.

## Grabar micrófono o audio del sistema (Chrome, apps, etc.)

La lista **Entrada** muestra dos tipos de fuentes:

- 🎤 **Micrófono / línea** — tu voz, instrumentos, etc.
- 🔊 **Captura de sistema** — lo que suena en el PC (Chrome, Spotify, videollamadas…)

**Cómo usarlo:**

1. Elige la **Entrada** adecuada:
   - Para grabar tu voz: elige tu micrófono (o deja "Predeterminada").
   - Para grabar lo que suena en el PC: elige la opción con 🔊.
2. Pulsa **● Grabar**.
3. **Mira la barra "Nivel"**: debe moverse cuando hay audio. Si no sube, elige otra Entrada.
4. Pulsa **■ Detener**. El archivo WAV se guarda y se agrega solo a la lista.

> Graba a la frecuencia nativa del dispositivo (o 48 kHz para audio de sistema) y mezcla
> a mono internamente; Whisper remuestrea solo.

Marca **"Transcribir automáticamente al detener"** para que, al pulsar ■ Detener, la
transcripción arranque sola con la configuración actual (modelo, idioma, formatos).

### Captura de audio del sistema por plataforma

| Plataforma | Soporte | Cómo |
|---|---|---|
| **Windows 10/11** | ✅ Nativo (WASAPI loopback vía librería `soundcard`) | Elige `🔊 … (audio del sistema)` en la lista. La primera vez la app ofrece instalar `soundcard` con un clic. |
| **Linux** | ✅ Nativo (PulseAudio / PipeWire) | Elige `🔊 Monitor of …` en la lista. Si no aparece: `pactl load-module module-loopback`. |
| **macOS** | ⚠️ Requiere driver virtual | Instala [BlackHole](https://existential.audio/blackhole/) (gratis) y selecciónalo como dispositivo de salida en preferencias de sonido; aparecerá en la lista como entrada. |

> **La primera vez que grabes**, si falta algún componente (`sounddevice` para
> micrófono, `soundcard` para audio de sistema en Windows), la app lo instala **en
> segundo plano con un clic**, sin congelar la ventana. En Linux necesitas además:
> `sudo apt install libportaudio2`.

## Arrastrar y soltar (opcional)

Para agregar audios arrastrándolos directo desde el explorador de archivos,
instala una vez el paquete opcional `tkinterdnd2`:

```
python -m pip install tkinterdnd2
```

(o edítalo dentro del entorno: `.venv/bin/pip install tkinterdnd2` en macOS/Linux,
`.venv\Scripts\pip install tkinterdnd2` en Windows). No es obligatorio: sin él, la
app funciona igual, simplemente sin esa función — no se agregó a `requirements.txt`
para no sumar una dependencia que no todos necesitan.

## Dónde quedan las grabaciones y transcripciones

Si no eliges una **carpeta de salida**, la app NUNCA guarda en carpetas temporales que
se borran al cerrar:

- Las **grabaciones** (micrófono o sistema) quedan en `desktop/grabaciones/`.
- Las **transcripciones** de audios descargados de YouTube (sin carpeta de salida
  elegida) quedan en `desktop/transcripciones/`.
- Las transcripciones de un archivo que ya tenías en el disco se guardan junto a ese
  archivo, como siempre.

Ambas carpetas se crean solas junto al programa y no se suben al repositorio.

## Llevarlo a otro equipo sin descargar de nuevo

En la versión ejecutada desde Python, los datos viven dentro de `desktop/`. En un
ejecutable PyInstaller se guardan junto al ejecutable cuando esa carpeta es escribible;
si el sistema la protege, se usa la carpeta de datos del usuario. La aplicación no usa
la carpeta temporal de extracción para grabaciones o transcripciones. Los entornos
virtuales no son portables entre equipos en general: para otro sistema operativo o una
instalación de Python incompatible, copia tus datos y vuelve a ejecutar `run.py`.

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
| "Falta el componente sounddevice/soundcard" al grabar | Acepta el aviso para instalarlo en el acto (se hace en segundo plano). En Linux instala además: `sudo apt install libportaudio2`. |
| La barra **Nivel** no se mueve | Elige otra **Entrada**; comprueba que el dispositivo no esté silenciado y que tienes permisos de micrófono. |
| No aparece "audio del sistema" en la lista (Windows) | Requiere Windows 10 build 2004+ (WASAPI). La entrada genérica aparece igual y ofrece instalar `soundcard` al usarla. |
| No aparece "Monitor of …" en la lista (Linux) | Ejecuta `pactl load-module module-loopback` y reinicia la app. |
| En macOS no hay opción de captura de sistema | Instala [BlackHole](https://existential.audio/blackhole/) y configúralo como salida de audio. |
| No aparece mi micrófono en la lista | Conéctalo antes de abrir la app y reiníciala; revisa los permisos de micrófono del sistema. |
| La primera transcripción tarda | Está descargando el modelo una sola vez; luego es rápido. |
