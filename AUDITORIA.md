# AUDITORÍA DEL REPOSITORIO — Transcriptor VtT

Fecha: 2026-07-08 · Alcance: rama `claude/voice-transcriber-multiplatform-6xifq1`
(rama por defecto, incluye los fixes de `codex/...` incorporados por fast-forward).

## 1. SPECIFICATIONS

- **STACK**: Escritorio: Python ≥ 3.8, Tkinter, faster-whisper (CTranslate2),
  yt-dlp, sounddevice/soundcard, numpy. Android: Kotlin, whisper.cpp v1.7.4
  (JNI/NDK), Material 3, minSdk 24 / arm64-v8a. CI: GitHub Actions (APK debug +
  release firmado opcional; checks de escritorio en 3 SO con pytest).
- **TARGET**: transcripción de voz a texto **100 % local y privada** (el audio
  nunca sale del equipo), instalable sin conocimientos técnicos, en PC
  (Windows/macOS/Linux) y Android.
- **CRITERIA**: Seguridad, Rendimiento, Mantenibilidad, Escalabilidad.

---

## MODULE A: [CRITICAL SEVERITY] BUGS & SECURITY

### A1. [CORREGIDO EN ESTA AUDITORÍA] Crash al arrancar en equipos con audio
`desktop/transcriptor_whisper.py` (UI, combobox de entradas): el desempaquetado
`[lbl for _, lbl, _, _ in self.entradas]` esperaba tuplas de **4** campos, pero
`_dispositivos_entrada()` devuelve tuplas de **5** desde que se agregó el origen
`"sd"/"sc"`. En cualquier equipo con ≥1 dispositivo de audio:
`ValueError: too many values to unpack` → **la app no abría**. Las pruebas bajo
Xvfb no lo detectaron porque el sandbox de CI no tiene dispositivos (lista vacía
→ el desempaquetado nunca se ejecuta). Corregido con el helper
`etiquetas_entradas_audio()` (fix aportado por la rama `codex`, incorporado, con
test de regresión y verificación bajo Xvfb simulando dispositivos reales).
**Lección**: los caminos dependientes de hardware necesitan pruebas con dobles
(la nueva prueba `test_etiquetas_entradas_audio_usa_tuplas_de_cinco_campos` cubre esto).

### A2. Falla silenciosa en la captura de audio del sistema
`desktop/transcriptor_whisper.py:870` (`_captura_loop_sistema`): el bucle entero
está envuelto en `try/except Exception: pass`. Si `soundcard` lanza a mitad de
grabación (dispositivo desconectado, cambio de salida predeterminada), el hilo
muere **en silencio**: la UI sigue diciendo "Grabando…", el medidor se congela y
el WAV queda truncado sin ningún aviso — la misma clase de falla ("archivo con
estática/vacío sin explicación") que motivó la reescritura de la grabación.
**Fix**: encolar el error a `self.cola` y detener la grabación con estado
"error" (bloque Antes/Después en Módulo C). **No aplicado** (esta entrega es
auditoría); aplicar en el siguiente ciclo.

### A3. Carrera en el cierre del hilo escritor (pérdida de cola del audio)
`desktop/transcriptor_whisper.py:891/932` (`_writer_grab` / `_cerrar_grabador`):
el cierre hace `join(timeout=2.0)` sobre el escritor y luego cierra
`self.wave_file` y pone `self.cola_grab = None`. Si el disco está lento y el
join expira: (a) el escritor sigue llamando `writeframes` sobre un archivo
cerrado (excepción tragada → se pierde la cola final de la grabación), o
(b) `self.cola_grab.get` sobre `None` → `AttributeError` que mata el hilo sin
registro. Probabilidad baja, pero es pérdida de datos. **Fix**: que el hilo
escritor sea dueño del cierre del archivo (Módulo C).

### A4. Endurecimiento de la cadena de suministro (CI y build nativo)
- `.github/workflows/*.yml`: todas las actions están ancladas por **tag móvil**
  (`actions/checkout@v4`, `softprops/action-gh-release@v2`, …). Un tag puede
  reapuntarse; anclar por **SHA de commit** elimina ese vector.
- `android/app/src/main/cpp/CMakeLists.txt:13`: whisper.cpp se descarga por
  `GIT_TAG v1.7.4` — los tags de git también son móviles; anclar al **hash de
  commit** del release.
- `desktop/requirements.txt`: rangos `>=` sin lockfile ni hashes; para el
  ejecutable PyInstaller conviene un `requirements.lock` con `--require-hashes`.
- Job `build-release`: escribe `keystore.properties` (contraseñas en claro) al
  workspace del runner. Aceptable en runners efímeros de GitHub, pero mejor
  pasar las claves como propiedades de Gradle vía entorno (`ORG_GRADLE_PROJECT_*`)
  sin tocar disco, y hacer `rm` del `.jks` al final del job.

### A5. Cuellos de botella conocidos y su mitigación actual
- Android: `AudioDecoder.decode()` retiene todo el PCM en memoria (~230 MB/hora
  a 16 kHz + pico intermedio). Mitigado: catch específico de `OutOfMemoryError`
  con mensaje accionable + aviso previo para audios > 90 min. La solución de
  fondo (decodificación/transcripción por bloques con solape) queda documentada
  como pendiente — requiere validación en dispositivo real que este entorno no
  permite.
- Escritorio: el Registro (`_escribe`, línea 1196) crece sin tope; en audios de
  horas con vista previa por segmento, el widget `Text` acumula decenas de miles
  de líneas y degrada la UI. **Fix barato**: recortar a las últimas N líneas
  (Módulo C).

Inyecciones (SQL/comando), manejo de secretos en el código de la app y
autenticación: **no se detectaron anomalías** (no hay SQL; los `subprocess` usan
listas de argumentos fijas, sin `shell=True`; no hay secretos hardcodeados —
verificado por grep; la app no tiene superficie de autenticación).

---

## MODULE B: [MEDIUM SEVERITY] REFACTOR & CLEAN CODE

### B1. Excepciones tragadas de forma sistemática
27 bloques `except Exception:` en `desktop/transcriptor_whisper.py`, la mayoría
con `pass` silencioso. Los de A2/A3 son los graves; el resto (config, ffmpeg,
explorador) es tolerable pero debería al menos registrarse (ver logging en C3).

### B2. Bug menor real: la consulta del host API pisa la frecuencia nativa
`desktop/transcriptor_whisper.py:792` (`_iniciar_grabacion_microfono`): si
`sd.query_hostapis(...)["name"]` lanza (clave ausente, índice raro), el `except`
del bloque resetea `rate, max_ch = 44100, 1` **descartando la frecuencia nativa
ya obtenida** — exactamente lo que ese código intenta evitar. Mover la consulta
del nombre del host API a un `try` anidado propio.

### B3. Clase Dios y violaciones de SRP
`TranscriptorApp` ≈ 1.100 líneas: UI + grabación (2 backends) + transcripción +
exportación + YouTube + config + tema. Extraer al menos `grabadora.py`
(callback/cola/escritor/dispositivos) y `exportadores.py` (`_fmt_md/srt/vtt`,
`envolver_texto`) — funciones ya casi puras y testeadas. Nota: `AGENTS.md`
declara la convención de archivo único; actualizar esa regla en el mismo cambio.

### B4. Cadena `if/elif` de 12 ramas en `_procesar_cola` (línea 1139)
Complejidad ciclomática alta y crece con cada mensaje nuevo. Reemplazar por
tabla de despacho `dict[str, Callable]` (Antes/Después en C2).

### B5. Tuplas posicionales de 5 campos como contrato de dispositivos
`("sd"|"sc", id, etiqueta, is_loopback, max_canales)` — el origen del crash A1.
Un `NamedTuple`/`dataclass` `EntradaAudio` con campos nombrados habría hecho el
error imposible de escribir. Es el refactor con mejor relación costo/beneficio.

### B6. Efectos secundarios en tiempo de import
`desktop/transcriptor_whisper.py:56`: `CARPETA_GRABACIONES.mkdir()` al importar
el módulo — importar no debería escribir en disco (molesta a linters, tests y
usos como librería). Mover a `main()`/`__init__` de la app.

### B7. Duplicación
- Los dos jobs de `android-build.yml` repiten 5 pasos idénticos de setup
  (JDK/SDK/NDK/CMake/Gradle) → extraer a una *composite action* local.
- `envolver_texto` (Python) y `envolverTexto` (Kotlin, `MainActivity.kt`)
  implementan la misma regla de negocio (ajuste a 100 columnas) sin ninguna
  prueba de paridad; documentar el contrato compartido o fijar casos de oro
  comunes en ambas suites.

### B8. Tipado y salidas
- Python sin type hints; con el mínimo en 3.8 se puede tipar gradualmente y
  verificar con mypy en el CI existente.
- `_escribir_salidas` (línea 1077) sobrescribe `.txt/.md/.srt/.vtt` existentes
  sin aviso: re-transcribir pisa silenciosamente un transcript que el usuario
  pudo haber editado. Sufijar (`nombre (2).txt`) o preguntar.

---

## MODULE C: [PROPOSALS] ENHANCEMENTS & COMPLEMENTS

### C1. Fix A2+A3 — captura y escritor robustos (Antes vs Después)

**Antes** (`_captura_loop_sistema`, esqueleto actual):
```python
def _captura_loop_sistema(self, mic, rate, canales):
    import numpy as np
    bloque = max(1, int(rate * 0.05))
    try:
        with mic.recorder(samplerate=rate, channels=canales, blocksize=bloque) as rec:
            while not self.grab_stop.is_set():
                ...
    except Exception:
        pass                      # <- el hilo muere y la UI sigue "Grabando…"
```

**Después**:
```python
def _captura_loop_sistema(self, mic, rate, canales):
    import numpy as np
    bloque = max(1, int(rate * 0.05))
    try:
        with mic.recorder(samplerate=rate, channels=canales, blocksize=bloque) as rec:
            while not self.grab_stop.is_set():
                ...
    except Exception:
        # Avisar a la UI (hilo de Tk) y detener la grabación con estado de error.
        self.cola.put(("grabacion_error",
                       "Se perdió la conexión con el dispositivo de captura."))
```
y en `_procesar_cola`: `"grabacion_error"` → `self._detener_grabacion()` +
`self._set_estado(msg, "error")`. Para A3, mover `wave_file.close()` al propio
hilo escritor (tras consumir el centinela `None`) y que `_cerrar_grabador` solo
señalice y espere; así el archivo nunca se cierra debajo del hilo que escribe.

### C2. Despacho de mensajes (Antes vs Después)

**Antes**: `if tipo == "log": ... elif tipo == "status": ...` (12 ramas).

**Después**:
```python
self._handlers = {
    "log":      lambda p: self._escribe(p),
    "status":   lambda p: (self._set_estado(p, "neutro"), self._escribe(p)),
    "progress": lambda p: self.pb.configure(value=p),
    ...
}
def _procesar_cola(self):
    try:
        while True:
            tipo, *p = self.cola.get_nowait()
            self._handlers.get(tipo, lambda p: None)(p[0] if p else None)
    except queue.Empty:
        pass
    self.root.after(120, self._procesar_cola)
```

### C3. Observabilidad y herramientas
- **Logging** (escritorio): módulo `logging` + `RotatingFileHandler` a
  `desktop/logs/app.log` (1 MB × 3); volcar allí todo lo que hoy se traga
  `except Exception`. Es el complemento natural del medidor de Nivel para
  diagnosticar problemas de audio de usuarios reales.
- **Lint/format en CI**: `ruff` (Python) en `desktop-check.yml`; `ktlint` o
  `detekt` (Kotlin) en `android-build.yml`.
- **Dependabot** para GitHub Actions y pip (cierra parte de A4).
- **Cobertura**: `pytest-cov` con umbral suave; smoke test Xvfb en el job Linux
  (los smokes que hoy se corren a mano, codificados como test marcado `ui`).
- **Recorte del Registro** (A5): en `_escribe`, si `self.log.index('end-1c')`
  supera ~5.000 líneas, `self.log.delete('1.0', '2000.0')`.

### C4. Rendimiento
- faster-whisper: exponer `device="auto"` (usa CUDA si existe) y `beam_size`
  como opciones avanzadas; hoy está fijo `cpu/int8`.
- Android: registrar `new_segment_callback` de whisper.cpp para vista previa en
  vivo como en PC (la infraestructura de callbacks JNI ya existe para progreso).

### C5. Integridad de modelos (complemento de la verificación por tamaño)
Calcular SHA-256 del modelo al terminar la descarga y guardarlo en el sidecar
junto al tamaño; verificar el hash (no solo `length`) al cargar tras un fallo de
`whisper_init`. Costo: una pasada de lectura solo cuando hay sospecha.

---

## Notas de esta auditoría

- La rama `codex/corrige-errores-y-bugs-en-el-repositorio` (2 commits: fix del
  crash A1 y `ruta_dentro_de` con `commonpath` para `_es_temporal`, que
  eliminaba un falso positivo por prefijo en Python 3.8) fue **incorporada por
  fast-forward** a esta rama antes de eliminarla, para no descartar correcciones
  válidas. Punta original: `6d2504d18471af696bb3d585a53122ed11db7180`.
- Verificación posterior al merge: `py_compile` OK, **15/15 pruebas** pasan,
  y arranque bajo Xvfb con dispositivos simulados (5 campos) sin errores.
- Los hallazgos A2, A3, B2 y B8 quedan **sin aplicar a propósito**: esta entrega
  es una auditoría; los parches propuestos están listos para ejecutarse como
  siguiente ciclo si se aprueban.
