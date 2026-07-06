# PLAN DE EJECUCIÓN MAESTRO — Transcriptor VtT

**Documento para ejecución por IA (Claude Sonnet).** Generado tras auditoría completa del
repositorio (escritorio Python/Tkinter + Android Kotlin/whisper.cpp + CI). Ejecutar las
tareas en orden de prioridad. Cada tarea es autocontenida: incluye archivos, instrucciones
y criterios de aceptación verificables.

---

## 0. Contexto del proyecto

| Componente | Stack | Estado |
|---|---|---|
| `desktop/` | Python 3.8+, Tkinter, faster-whisper, yt-dlp, sounddevice; auto-instalador `run.py` (venv local) | Funcional; grabación de sistema **rota en Windows** (H1) |
| `android/` | Kotlin, Material 3, whisper.cpp v1.7.4 vía CMake FetchContent + JNI, arm64-v8a, minSdk 24 | Compila en CI; riesgos de ciclo de vida (H8) |
| `.github/workflows/` | `android-build.yml` (APK + release rodante), `desktop-build.yml` (PyInstaller manual) | Verde; ejecutable de PC no incluiría grabación (H4) |

Propuesta de valor del producto: **transcripción 100 % local y privada, instalable sin
conocimientos técnicos, que descarga sola lo que necesita.**

---

## 1. Hallazgos de la auditoría (Fase 1)

Severidad: 🔴 rompe funcionalidad prometida / pérdida de datos · 🟠 defecto de robustez · 🟡 calidad/mejora.

### H1 🔴 Captura de audio del sistema ROTA en Windows
`desktop/transcriptor_whisper.py` usa `sd.WasapiSettings(loopback=True)`. **Verificado
contra el código fuente de sounddevice 0.5.5 (versión actual): `WasapiSettings.__init__`
solo acepta `exclusive`, `auto_convert`, `explicit_sample_format`.** La llamada lanza
`TypeError`; el código solo captura `AttributeError`, así que el usuario ve "No se pudo
abrir el dispositivo". PortAudio (el backend de sounddevice) no soporta loopback WASAPI.
**La función principal pedida por el usuario —transcribir lo que suena en Chrome u otra
app— no funciona en Windows hoy.** → Tarea T1.

### H2 🔴 Pérdida de datos: grabaciones y transcripciones en carpetas temporales
Si no hay "Carpeta de salida" configurada, `_iniciar_grabacion()` guarda el WAV en
`tempfile.mkdtemp()` registrado en `self.temp_dirs`, y `_escribir_salidas()` escribe los
`.txt/.md/...` junto al audio (es decir, dentro del temporal). `_cerrar()` hace
`shutil.rmtree` de esos directorios: **al cerrar la app se borran la grabación Y sus
transcripciones**. Lo mismo aplica al audio bajado de YouTube. → Tarea T2.

### H3 🔴 Fricción de instalación: el marcador del venv no detecta dependencias nuevas
`run.py` instala dependencias solo si no existe `.venv/.deps_ok`. Al añadir `sounddevice`
a `requirements.txt`, los usuarios con venv previo NO la reciben (causa exacta del reporte
del usuario: "para grabar debo actualizar e instalar otra dependencia"). Además,
`_asegurar_sounddevice()` ejecuta `pip install` **bloqueando el hilo de Tk** (la ventana
se congela, "no responde") y ese camino es imposible dentro de un ejecutable PyInstaller
(`sys.frozen`). `numpy` se usa en la grabación pero no está declarado en
`requirements.txt` (llega solo por transitividad). → Tarea T3.

### H4 🟠 El ejecutable PyInstaller no incluiría la grabación
`desktop-build.yml` no tiene `--collect-all sounddevice` (ni soundcard/numpy): el binario
generado no podría grabar y el auto-instalador en caliente no funciona congelado. → T3/T8.

### H5 🟠 Lista de entradas duplicada y confusa en Windows
`_dispositivos_entrada()` recorre TODOS los host APIs de PortAudio (MME, DirectSound,
WASAPI, WDM-KS): cada micrófono aparece 3–4 veces con nombres truncados distintos. Elegir
el duplicado equivocado es la causa más probable de la grabación con estática que reportó
el usuario. → Tarea T4.

### H6 🟠 Combobox de entrada demasiado angosto (width=32) para nombres reales de dispositivos.

### H7 🟠 Estados de color fuera de la paleta
`lbl_st`/`lbl_ff` usan colores crudos `"gray"`, `"red"`, `"green"` en vez de `PALETA`;
`_finalizar()` decide el estado inspeccionando el texto del label (`"ancelad" in text`),
lo cual es frágil. → Tarea T9.

### H8 🟠 Android: use-after-free y pérdida de trabajo al rotar la pantalla
`MainActivity.onDestroy()` llama `transcriber.free()` mientras una corrutina puede estar
dentro de `whisper_full` (la llamada nativa NO es cancelable por `lifecycleScope`):
liberar el contexto en uso = crash nativo. Además, rotar la pantalla recrea la Activity y
pierde el resultado/estado. → Tarea T5.

### H9 🟠 Android: sin verificación de integridad del modelo
`ModelManager.isDownloaded()` acepta cualquier archivo > 1 MB. Sin verificación de tamaño
esperado ni checksum; sin reanudación de descargas (466 MB de `small` se rebajan enteros
tras un corte). → Tarea T13.

### H10 🟠 Android: audio completo en memoria
`AudioDecoder` acumula todo el PCM en un `ByteArrayOutputStream` y devuelve un
`FloatArray` completo (1 h de audio ≈ 230 MB + pico intermedio del doble): riesgo de OOM
en audios largos. → Tarea T15 (P3, documentar límite mientras tanto).

### H11 🟡 Android: icono de launcher genérico (`sym_def_app_icon`), sin marca. → T11.

### H12 🟡 CI Android ancla la rama de trabajo `claude/...` en `on.push.branches`; limpiar al fusionar a `main`. → T7.

### H13 🟡 Sin pruebas automatizadas ni archivo de reglas del repo (las convenciones viven
solo en los README). → Tarea T7.

### H14 🟡 README raíz desactualizado: dice que el PC graba "desde el micrófono/entrada";
ya se promete también captura del sistema. Mantener consistencia de claims. → T1 (docs).

---

## 2. Expansión de valor (Fase 2) — resumen de decisiones

- **UX escritorio**: vista previa del texto en vivo durante la transcripción (los
  segmentos ya llegan en streaming en `_worker`), ETA, opción "transcribir al detener la
  grabación", progreso de descarga de YouTube. Modo oscuro con la paleta ya definida.
- **UX Android**: recibir audio compartido desde otras apps (intent `ACTION_SEND`/`VIEW`)
  — el flujo natural en móvil es "Compartir → Transcriptor"; guardar el resultado como
  `.txt`; progreso y cancelación reales vía callbacks de whisper.cpp; icono propio.
- **Procesos**: archivo de reglas `AGENTS.md`, workflow de CI de escritorio (py_compile +
  pytest en 3 SO), hash de requirements en el marcador del venv.
- **Descartado tras el sanity check** (Fase 3): reescribir el escritorio en otro
  framework (Qt/web) — rompe la regla "solo Python estándar + pip"; `pyaudiowpatch` para
  loopback — solo Windows y duplica PortAudio (se elige `soundcard`, más liviana y
  multiplataforma); grabación loopback en macOS sin driver — imposible sin extensión de
  sistema (se documenta BlackHole).

---

## 3. Reglas inquebrantables (verificar en CADA tarea)

1. **Offline-first y privado**: el audio nunca sale del equipo. Solo se descargan
   dependencias y modelos, una vez.
2. **Instalación sin fricción**: PC = solo Python + doble clic; Android = solo el APK.
   Ninguna tarea puede añadir pasos manuales de instalación (excepto los ya documentados:
   `libportaudio2` en Linux, BlackHole en macOS).
3. **Portabilidad de carpeta (PC)**: todo vive dentro de `desktop/` (venv, config,
   grabaciones); copiar la carpeta = mover la instalación.
4. **Sin privilegios de administrador** en ningún flujo.
5. **Idioma**: UI, comentarios, commits y docs en **español**. Nombres de código
   existentes (funciones/variables en español) se respetan.
6. **Paleta**: violeta `#6C4DF2` como primario en ambas plataformas (escritorio `PALETA`,
   Android `colors.xml` claro/oscuro). No introducir colores fuera del sistema.
7. **Compatibilidad**: escritorio Python ≥ 3.8, Windows/macOS/Linux; Android minSdk 24,
   arm64-v8a. No subir estos mínimos.
8. **No versionar** binarios, `.venv`, `build/`, modelos ni APKs (respetar `.gitignore`).
9. **Rama de trabajo**: `claude/voice-transcriber-multiplatform-6xifq1` (hasta que el
   dueño indique otra). Commits atómicos por tarea, mensaje en español.
10. **Dependencias**: mínimas y con versión mínima anclada en `requirements.txt`. Antes de
    usar una API de una librería, **verificar su firma real en la versión actual** (el
    error H1 nació de asumir una API inexistente).

---

## 4. Roadmap priorizado (Fase 4)

Formato: **Tn (Prioridad) — Título**. Impacto/Esfuerzo en escala A(lto)/M(edio)/B(ajo).
Ejecutar en este orden; T1–T3 son bloqueantes antes de cualquier otra cosa.

---

### T1 (P0) — Reparar captura de audio del sistema en Windows
**Impacto A / Esfuerzo M** · Archivos: `desktop/transcriptor_whisper.py`,
`desktop/requirements.txt`, `desktop/README.md`, `README.md`.

La técnica actual (`sd.WasapiSettings(loopback=True)`) no existe. Sustituir por la
librería **`soundcard`** (pip, sin binarios del sistema; habla directo con
WASAPI/PulseAudio/CoreAudio) **solo para las fuentes loopback de Windows**:

1. Añadir `soundcard>=0.4.2` a `requirements.txt` (mantener `sounddevice` para micrófonos
   y monitores de Linux).
2. En `_dispositivos_entrada()`: en Windows, listar además
   `soundcard.all_microphones(include_loopback=True)` y añadir solo las que tengan
   `isloopback == True` como entradas `(id_str, "🔊 <nombre> (audio del sistema)",
   "loopback_sc", canales)`. Marcar el origen de cada entrada (`"sd"` o `"sc"`).
3. En `_iniciar_grabacion()`: si la fuente es `"sc"`, grabar en un hilo dedicado con
   `mic.recorder(samplerate=48000, channels=2)` + bucle `rec.record(1024)` → convertir
   float32 [-1,1] a int16 → **encolar en la misma `cola_grab`** (el hilo escritor y el
   medidor de nivel existentes no cambian). El flag `self.grabando` detiene el bucle.
4. En Linux mantener los monitores (`monitor` en el nombre) como hasta ahora; en macOS,
   si no hay dispositivo virtual, el README ya documenta BlackHole.
5. Manejar la ausencia de `soundcard` igual que `sounddevice` (instalación al vuelo de T3).
6. Actualizar la línea de Funciones del `README.md` raíz (H14) para reflejar micrófono +
   audio del sistema con sus requisitos por SO.

**Criterios de aceptación**
- `python -m py_compile desktop/transcriptor_whisper.py` pasa.
- Prueba simulada (sin hardware): inyectar bloques float32 estéreo por el camino `"sc"` y
  verificar que el WAV resultante es int16 mono con el RMS esperado (reutilizar el patrón
  de test de tubería ya usado en el repo).
- En Windows real: elegir una entrada 🔊, reproducir audio en Chrome, la barra Nivel se
  mueve y el WAV contiene el audio (verificación manual del dueño; dejar registro en el
  log de la app de fuente y frecuencia usadas).
- Ninguna llamada a `WasapiSettings` queda en el código.

---

### T2 (P0) — Eliminar la pérdida de datos de grabaciones/salidas temporales
**Impacto A / Esfuerzo B** · Archivos: `desktop/transcriptor_whisper.py`, `desktop/README.md`, `.gitignore`.

1. Crear carpeta persistente `desktop/grabaciones/` (crear con `mkdir(exist_ok=True)`;
   añadir a `.gitignore`). Las grabaciones SIEMPRE se guardan ahí cuando no hay carpeta
   de salida válida configurada (nunca más en `tempfile.mkdtemp`).
2. En `_escribir_salidas()`: si el audio de origen está dentro de un directorio de
   `self.temp_dirs` (caso YouTube) y no hay carpeta de salida, escribir las salidas en
   `desktop/transcripciones/` (persistente, en `.gitignore`) en lugar de junto al audio.
3. `_cerrar()` sigue limpiando solo los temporales de YouTube (audio re-descargable).
4. Documentar ambas carpetas en `desktop/README.md`.

**Criterios de aceptación**
- Test: grabar (simulado) sin carpeta de salida → el WAV queda en `grabaciones/` y existe
  tras simular el cierre (`_cerrar` sin destroy en test o verificación de rutas).
- Test: transcribir un archivo ubicado en un temp_dir sin salida configurada → los
  `.txt/.md` aparecen en `transcripciones/`.
- `git status` no muestra las carpetas nuevas (ignoradas).

---

### T3 (P0) — Instalación de dependencias robusta y sin fricción
**Impacto A / Esfuerzo M** · Archivos: `desktop/run.py`, `desktop/requirements.txt`,
`desktop/transcriptor_whisper.py`.

1. `requirements.txt`: añadir `numpy>=1.24` y `soundcard>=0.4.2` (de T1) con comentario.
2. `run.py`: sustituir el marcador `.deps_ok` por `.deps_ok` **con el SHA-256 de
   `requirements.txt` como contenido**; si el hash guardado difiere del actual,
   reinstalar automáticamente ("Actualizando dependencias nuevas…"). `--update` sigue
   forzando.
3. `_asegurar_sounddevice()` (generalizar a `_asegurar_grabacion()` que cubre
   sounddevice + soundcard + numpy):
   - Si `getattr(sys, "frozen", False)`: NO intentar pip; mostrar mensaje "esta versión
     ejecutable no incluye grabación; usa run.py" (hasta que T8 la incluya, entonces este
     camino no ocurrirá).
   - Ejecutar el `pip install` en un `threading.Thread` con botón deshabilitado y estado
     en `lbl_st` vía `self.cola` (NUNCA bloquear el mainloop); al terminar, reintentar el
     import y continuar la acción del usuario.

**Criterios de aceptación**
- Test unitario del hash: marcador viejo/ausente/distinto → reinstala; igual → no.
- `py_compile` pasa; arrancar la app sin sounddevice instalado muestra el diálogo y la UI
  sigue respondiendo (verificable manualmente; en test, cubrir la rama `frozen`).
- Un usuario con venv antiguo ejecuta `run.py` y recibe las dependencias nuevas sin pasos
  manuales.

---

### T4 (P1) — Lista de entradas limpia y correcta (Windows sobre todo)
**Impacto M / Esfuerzo B** · Archivos: `desktop/transcriptor_whisper.py`.

1. En Windows, listar solo los dispositivos del host API **WASAPI** (buscar en
   `sd.query_hostapis()`; si no existe, usar el host API por defecto). Elimina los
   duplicados MME/DirectSound/WDM-KS (H5).
2. Ampliar el Combobox a `width=48` (H6) y dejar el ancho del popup al del texto.
3. Registrar en el log de la app el dispositivo, host API y frecuencia al iniciar cada
   grabación (diagnóstico de soporte).

**Criterios de aceptación**
- En Windows la lista muestra cada micrófono UNA vez + entradas 🔊 de T1.
- `py_compile` pasa; en Linux/macOS la lista no cambia salvo el ancho.

---

### T5 (P1) — Android: ciclo de vida seguro (sin crash nativo, sin perder trabajo)
**Impacto A / Esfuerzo M** · Archivos: `android/.../MainActivity.kt`, `Transcriber.kt`,
nuevo `TranscribeViewModel.kt`, `app/build.gradle`.

1. Crear `TranscribeViewModel` (`androidx.lifecycle:lifecycle-viewmodel-ktx`): posee el
   `Transcriber`, el estado (`StateFlow` de: ocioso/descargando(pct)/procesando/resultado/
   error) y lanza el trabajo en `viewModelScope`. La Activity solo observa y pinta.
2. `Transcriber`: hacer `loadModel/transcribe/free` seguros entre hilos (`@Synchronized`
   o mutex); `free()` no libera mientras `transcribe` está en curso (esperar o marcar
   liberación diferida). Liberar en `ViewModel.onCleared()`.
3. Mantener la pantalla encendida durante el trabajo
   (`window.addFlags(FLAG_KEEP_SCREEN_ON)` mientras el estado sea activo).

**Criterios de aceptación**
- Compila en CI (`gradle assembleDebug` verde).
- Rotar la pantalla durante una transcripción: no crashea, el progreso continúa y el
  resultado aparece al terminar (verificación manual; en el código, `free()` nunca puede
  ejecutarse concurrente con `transcribe` por construcción — revisable estáticamente).

---

### T6 (P1) — Android: recibir audio compartido desde otras apps
**Impacto A / Esfuerzo B** · Archivos: `AndroidManifest.xml`, `MainActivity.kt`.

1. Añadir intent-filters a MainActivity: `ACTION_SEND` (con `EXTRA_STREAM`) y
   `ACTION_VIEW` para `audio/*` y `video/*`.
2. En `onCreate`/`onNewIntent`, si llega un URI, seleccionarlo como archivo actual
   (mismo camino que el picker) y mostrar su nombre.

**Criterios de aceptación**
- CI verde. Desde WhatsApp/Chrome "Compartir → Transcriptor VtT" abre la app con el
  audio ya seleccionado y el botón Transcribir habilitado (manual).

---

### T7 (P1) — Reglas del repo + CI de escritorio + pruebas mínimas
**Impacto M / Esfuerzo B** · Archivos: nuevo `AGENTS.md` (raíz), nuevo
`.github/workflows/desktop-check.yml`, nuevo `desktop/tests/test_pipeline.py`,
`android-build.yml`.

1. `AGENTS.md`: volcar la sección 3 de este plan (reglas inquebrantables) + convenciones
   (español, paleta, estructura). Es el contrato para futuros agentes.
2. `desktop-check.yml`: en cada push que toque `desktop/**`: matriz ubuntu/windows/macos,
   `python -m py_compile desktop/*.py` + `pytest desktop/tests -q` (sin instalar
   faster-whisper: los tests no lo importan).
3. `test_pipeline.py`: (a) test del hilo escritor de grabación con tono sintético
   (RMS/frecuencia/descarte inicial — patrón ya validado en la sesión); (b) test de
   `envolver_texto` (líneas ≤ 100, párrafos preservados); (c) test del hash de
   requirements de T3; (d) test de rutas de T2.
4. `android-build.yml`: quitar la rama `claude/...` cuando este trabajo se fusione a
   `main` (dejar comentario TODO si aún no se fusiona).

**Criterios de aceptación**
- El workflow nuevo corre verde en los 3 SO en el push de esta tarea.
- `pytest` local: 4+ tests, todos pasan sin dependencias pesadas instaladas.

---

### T8 (P1) — Ejecutables PyInstaller completos
**Impacto M / Esfuerzo B** · Archivos: `.github/workflows/desktop-build.yml`.

1. Añadir `--collect-all sounddevice --collect-all soundcard --collect-all numpy` (y
   `--hidden-import` que haga falta) al comando PyInstaller.
2. Instalar también esas libs en el paso previo (ya vienen por requirements).

**Criterios de aceptación**
- Ejecutar el workflow manualmente: 3 artefactos generados; el binario de Linux arranca
  en el runner con `xvfb-run` hasta pintar la ventana (smoke test añadido al workflow) o,
  como mínimo, `--collect-all` no rompe el build en ningún SO.

---

### T9 (P2) — Escritorio: estados visuales del sistema de diseño + preview en vivo
**Impacto M / Esfuerzo M** · Archivos: `desktop/transcriptor_whisper.py`.

1. Añadir a `PALETA`: `ok` (#2E9E6B), `error` (#D64550), `warn` (#C7862B) y usar SIEMPRE
   estilos ttk (`Estado.Ok.TLabel`, etc.) en vez de `foreground="gray"/"red"/"green"`
   (H7). `_finalizar()` decide por una variable de estado, no por el texto del label.
2. Vista previa en vivo: los segmentos que llegan en `_worker` se envían por la cola
   (`("segmento", texto)`) y se muestran en el panel Registro con formato compacto, más
   ETA calculado (`seg.end/dur` vs tiempo transcurrido) en `lbl_st`.
3. Checkbox "Transcribir automáticamente al detener la grabación" (persistido en config).

**Criterios de aceptación**
- Sin ocurrencias de `foreground="red"|"green"|"gray"` en el archivo (grep).
- `py_compile` + tests verdes. ETA visible durante transcripción (manual).

---

### T10 (P2) — Escritorio: progreso de YouTube y modo oscuro
**Impacto M / Esfuerzo M** · Archivos: `desktop/transcriptor_whisper.py`.

1. Hook de progreso de yt-dlp → cola → `pb` + `lbl_st` ("Descargando… 43 %").
2. Paleta oscura (`PALETA_OSCURA`) + botón alternador 🌙 persistido en config;
   `_aplicar_estilo(root, paleta)` parametrizada; Listbox/ScrolledText re-coloreados.

**Criterios de aceptación**
- Alternar tema re-pinta todos los contenedores sin reiniciar (manual); preferencia
  sobrevive al reinicio (test del snapshot de config). CI verde.

---

### T11 (P2) — Android: progreso real, cancelar, guardar .txt e icono propio
**Impacto A / Esfuerzo M** · Archivos: `whisper_jni.cpp`, `WhisperBridge.kt`,
`Transcriber.kt`, `TranscribeViewModel.kt`, `MainActivity.kt`, `activity_main.xml`,
recursos mipmap.

1. JNI: registrar `wparams.progress_callback` y `wparams.abort_callback` de whisper.cpp;
   exponer progreso (0–100) vía callback JNI a Kotlin y un `AtomicBoolean` de aborto.
2. UI: barra determinada durante la transcripción; botón "Cancelar" visible mientras
   trabaja; botón "Guardar .txt" con `ActivityResultContracts.CreateDocument` (el texto
   se escribe envuelto a 100 columnas, coherente con el PC).
3. Icono adaptativo propio: micrófono blanco sobre fondo violeta `#6C4DF2`
   (vector XML, `mipmap-anydpi-v26`), reemplazando `sym_def_app_icon` (H11).

**Criterios de aceptación**
- CI verde. Cancelar detiene el trabajo en < 2 s y libera la UI (manual). El progreso
  avanza durante la transcripción (manual). El APK muestra el icono violeta.

---

### T12 (P2) — Android: verificación e integridad de modelos
**Impacto M / Esfuerzo B** · Archivos: `ModelManager.kt`.

1. Tabla de tamaños esperados (bytes exactos de HF para tiny/base/small);
   `isDownloaded()` exige tamaño exacto (±0) en lugar de "> 1 MB" (H9).
2. Reanudación: si existe `.part`, reintentar con cabecera `Range` y continuar.
3. Si un archivo existente no cuadra con el tamaño esperado, borrarlo y re-descargar
   (con mensaje "El modelo estaba corrupto, descargando de nuevo…").

**Criterios de aceptación**
- CI verde. Unit test JVM simple para la lógica de decisión (tamaño esperado/parcial) si
  se extrae a función pura; si no, revisión estática + prueba manual de descarga cortada.

---

### T13 (P3) — Android: audios largos sin OOM
**Impacto M / Esfuerzo A** · `AudioDecoder.kt`, `Transcriber.kt`, JNI.

Procesar por bloques de ~10 min con solape de 5 s: decodificar incrementalmente
(el decodificador emite trozos PCM → downmix/resample al vuelo) y llamar a
`whisper_full` por bloque concatenando resultados. Mientras no se haga, `MainActivity`
debe capturar `OutOfMemoryError` y sugerir un audio más corto.

**Criterios**: transcribir un audio de 2 h en un equipo de 4 GB sin crash (manual);
CI verde.

---

### T14 (P3) — Firma de release y pulido de distribución
`android-build.yml` + `app/build.gradle`: job opcional `assembleRelease` firmado con
keystore en secrets (`ANDROID_KEYSTORE_B64`, `ANDROID_KEYSTORE_PASS`); documentar en
README cómo generar el keystore. Mantener el APK debug como camino simple.

### T15 (P3) — Extras de escritorio
Arrastrar y soltar archivos (si `tkinterdnd2` está disponible; degradar sin él), atajos
de teclado (Ctrl+O/Ctrl+R/Ctrl+Enter), historial de salidas con botón abrir.

---

## 5. Protocolo de verificación global (aplicar al cerrar cada tarea)

1. `python -m py_compile desktop/*.py` (si tocó escritorio).
2. `pytest desktop/tests -q` (desde T7 en adelante).
3. Si tocó `android/`: esperar el workflow "Android APK" verde antes de dar por cerrada
   la tarea; si falla, corregir antes de continuar.
4. Revisar que no se violó ninguna regla de la sección 3 (especialmente 1–4 y 10).
5. Commit atómico en español describiendo el "porqué", push a la rama de trabajo.
6. Actualizar los README afectados EN EL MISMO commit (las claims de los docs nunca
   pueden adelantarse a la funcionalidad real — ver H1/H14).

## 6. Soluciones descartadas (no reintentar)

- `sd.WasapiSettings(loopback=True)` / cualquier loopback vía sounddevice-PortAudio: la
  API no existe (verificado en 0.5.5).
- `pyaudiowpatch` para loopback: solo Windows, duplica el stack de PortAudio.
- Grabar la salida en macOS sin driver virtual: imposible sin extensión del sistema;
  BlackHole documentado es la vía soportada.
- Reescritura del escritorio a Qt/Electron/web: viola las reglas 2 y 3.
- Subir minSdk o añadir ABIs x86 al APK: fuera del alcance del producto.
