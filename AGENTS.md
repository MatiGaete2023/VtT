# AGENTS.md — Reglas del repositorio VtT

Contrato para cualquier agente (humano o IA) que modifique este repositorio.
Léelo antes de tocar código. Si un cambio viola una regla de aquí, no se hace
sin antes discutirlo explícitamente.

## Qué es este proyecto

Transcriptor de voz a texto **local y privado** con Whisper, en dos plataformas:

- `desktop/` — Python + Tkinter, para Windows/macOS/Linux.
- `android/` — Kotlin + whisper.cpp nativo (JNI), APK 100 % offline.

## Reglas inquebrantables

1. **Offline-first y privado.** El audio del usuario nunca sale del equipo.
   Solo se permite red para: descargar dependencias (una vez) y descargar
   modelos de Whisper (una vez, con caché local).
2. **Instalación sin fricción.**
   - PC: el usuario solo necesita Python instalado + doble clic en
     `run.bat`/`run.sh`/`python run.py`. Nada de pasos manuales adicionales,
     salvo los ya documentados (PortAudio en Linux, BlackHole en macOS para
     capturar audio de sistema).
   - Android: el usuario solo instala el APK generado por CI.
   - Cualquier dependencia nueva debe quedar declarada en
     `desktop/requirements.txt` — el lanzador (`run.py`) la detecta e instala
     sola por el hash del archivo; no dependas de que el usuario recuerde
     ejecutar `--update`.
3. **Portabilidad de carpeta (PC).** Todo lo que la app necesita (entorno
   virtual, config, grabaciones) vive dentro de `desktop/`. Copiar la carpeta
   a otro equipo debe funcionar. No escribas fuera de `desktop/` ni en rutas
   fuera del proyecto salvo la caché de HuggingFace/PortAudio (fuera de
   nuestro control).
4. **Sin privilegios de administrador** en ningún flujo de instalación o uso.
5. **Nunca pierdas el trabajo del usuario.** Grabaciones y transcripciones sin
   carpeta de salida configurada van a `desktop/grabaciones/` y
   `desktop/transcripciones/` (persistentes, en `.gitignore`) — nunca a una
   carpeta temporal que se borre al cerrar la app.
6. **Idioma:** UI, mensajes al usuario, comentarios y commits en **español**.
   Los identificadores de código existentes en español se respetan (no se
   traducen a mitad de camino).
7. **Paleta de color:** violeta `#6C4DF2` como color primario en ambas
   plataformas (`PALETA` en `transcriptor_whisper.py`, `colors.xml` en
   Android, con sus variantes claro/oscuro). No introduzcas colores fuera del
   sistema de diseño existente.
8. **Compatibilidad mínima:** Python ≥ 3.8 en escritorio; Android `minSdk 24`,
   arquitectura `arm64-v8a`. No subas estos mínimos sin justificarlo.
9. **No versionar** binarios, `.venv/`, `build/`, modelos descargados ni APKs
   (ver `.gitignore`). Si agregas una carpeta persistente nueva de datos de
   usuario, agrégala al `.gitignore`.
10. **Verifica las APIs de terceros antes de usarlas.** No asumas la firma de
    una función de una librería externa: léela en el código fuente instalado
    o en la documentación oficial de la versión que estás fijando en
    `requirements.txt`/`build.gradle`. (Un error de este tipo — asumir que
    `sounddevice.WasapiSettings` aceptaba `loopback=True`, cuando esa API no
    existe — rompió la captura de audio de sistema en una versión anterior.)

## Convenciones de código

- **Escritorio:** un único archivo `transcriptor_whisper.py` con la clase
  `TranscriptorApp`. Comunicación entre hilos de trabajo y la UI de Tk
  siempre vía `self.cola` (una `queue.Queue` drenada por `_procesar_cola`,
  que corre en el hilo de Tk vía `root.after`). Nunca toques un widget de Tk
  desde un hilo que no sea el principal.
- **Android:** el trabajo de transcripción vive en un `ViewModel`
  (`TranscribeViewModel`, `viewModelScope`) para sobrevivir a la rotación de
  pantalla. `Transcriber` sincroniza `loadModel`/`transcribe`/`free` sobre el
  mismo monitor para que liberar el contexto nativo nunca ocurra mientras
  hay una transcripción en curso.

## Cómo verificar un cambio antes de darlo por terminado

1. Si tocaste `desktop/*.py`:
   ```
   python -m py_compile desktop/*.py
   pytest desktop/tests -q
   ```
2. Si tocaste `android/`: espera a que el workflow **"Android APK"** termine
   en verde en GitHub Actions antes de considerar la tarea cerrada. No hay
   forma de compilar Kotlin/Gradle localmente en muchos entornos de agente;
   el CI es la única verificación real de que compila.
3. Actualiza los README afectados **en el mismo commit** que el cambio de
   código. Un README no puede prometer una función que el código todavía no
   hace (o ya no hace).
4. Commits atómicos, mensaje en español, explicando el *porqué* del cambio.

## Qué NO hacer

- No reescribas el escritorio en otro framework (Qt/Electron/web): viola la
  regla de "solo Python + pip, sin fricción".
- No agregues loopback de audio vía `sounddevice`/PortAudio: esa API no
  existe. Usa `soundcard` (WASAPI en Windows) o los "monitor" de
  PulseAudio/PipeWire ya expuestos como entradas normales en Linux.
- No subas `minSdk` de Android ni agregues ABIs x86 sin que el usuario lo
  pida explícitamente (el objetivo es un APK liviano para teléfonos ARM
  actuales).
- No agregues telemetría, analytics ni ninguna llamada de red que no sea
  descarga de dependencias/modelos.
