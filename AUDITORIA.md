# AUDITORÍA DEL REPOSITORIO — VtT

**Actualizada y cerrada:** 9 de septiembre de 2026  
**Rama auditada:** `claude/voice-transcriber-multiplatform-6xifq1`  
**Base funcional V5.1 al iniciar esta revisión:** `aa1b8d8b5407869d55225c46bf3b199d00b72e3d`

Esta auditoría sustituye la revisión antigua de julio. Los defectos ya corregidos se separan de los límites que permanecen abiertos; las pruebas automatizadas y de empaquetado ejecutadas en el cierre se registran al final.

## 1. Estado ejecutivo

### Escritorio

Estado: **funcional y modularizado, V5.1**.

- Python mínimo real: **3.9+**.
- Entry point: `desktop/vtt_main.py`.
- ASR: `faster-whisper` / CTranslate2.
- Diarización: `sherpa-onnx`, perfiles Rápida/Equilibrada/Precisa.
- Auto estructural, worker persistente, alineación por palabra y división por cambio de voz.
- V5.1 añade verificación acústica conservadora de identidad, escaneo local acotado y confianza por identidad.
- JSON maestro: **schema v6**.
- CI de escritorio: `py_compile + pytest` en Windows/macOS/Ubuntu.
- PyInstaller V5.1 verificado en Windows/macOS/Ubuntu.

### Android

Estado: **funcional para ASR local; no tiene diarización V5.1**.

- Kotlin + whisper.cpp/JNI.
- `minSdk 24`, ARM64.
- Progreso y cancelación nativa.
- El trabajo vive en `TranscribeViewModel`; `Transcriber` sincroniza carga/transcripción/liberación.
- Admite ACTION_SEND/ACTION_VIEW para audio y video.
- TXT/SRT, persistencia del último documento y texto editado separado del original.
- Descargas de modelo reanudables y protección de integridad local por tamaño + SHA-256 calculado tras la descarga.
- whisper.cpp fijado al commit exacto `8a9ad7844d6e2a10cddf4b92de4089d7ac2b14a9` (tag oficial v1.7.4 verificado al cierre).
- Workflow Android con permisos reducidos por job y limpieza explícita del material de firma temporal.

## 2. Hallazgos antiguos que ya están corregidos

### [CORREGIDO] Captura de audio del sistema en Windows

La implementación actual usa `soundcard` para loopback WASAPI y mantiene `sounddevice` para micrófonos. Ya no depende de una supuesta `WasapiSettings(loopback=True)`.

### [CORREGIDO] Pérdida de grabaciones/transcripciones temporales

Las grabaciones sin salida explícita usan almacenamiento persistente. Las transcripciones de medios descargados a un directorio temporal se redirigen a la carpeta persistente de transcripciones.

### [CORREGIDO] Dependencias nuevas no detectadas por el venv

`run.py` guarda el SHA-256 de `requirements.txt`, comprueba importabilidad y reinstala cuando cambia el archivo o falta un módulo. `--update`/`--repair` fuerzan reparación.

### [CORREGIDO] Instalación de dependencias de grabación congelando Tk

La instalación bajo la aplicación se realiza mediante un hilo y la respuesta vuelve por la cola de UI. Un ejecutable congelado no intenta ejecutar `pip`.

### [CORREGIDO] Cierre inseguro del WAV

El hilo escritor conserva referencias locales a cola/WAV, consume un centinela y es el único dueño del cierre del archivo. La UI no fuerza el cierre si el writer sigue vivo.

### [CORREGIDO] Fallo silencioso del loopback

La captura `soundcard` encola `grabacion_error` si el hilo falla y la UI conserva el WAV parcial cuando es posible.

### [CORREGIDO] Frecuencia nativa descartada por consulta del host API

La consulta descriptiva del host API está separada de la lectura de frecuencia/canales; un fallo descriptivo no pisa la frecuencia ya obtenida.

### [CORREGIDO] Sobrescritura silenciosa de exportaciones

La familia de archivos usa un tronco disponible y añade `(2)`, `(3)`, etc. si ya existe una salida.

### [CORREGIDO] Android use-after-free por rotación

El trabajo está en `TranscribeViewModel`; `loadModel`, `transcribe` y `free` se sincronizan en `Transcriber`. `onCleared()` solicita aborto y libera en otro hilo.

### [CORREGIDO] Android sin reanudación/integridad local de modelos

`ModelManager` usa `.part`, `Range`, valida `Content-Range`, conserva tamaño y SHA-256 local y detecta corrupción posterior.

## 3. Hallazgos V5.1

### A1. [CORREGIDO] Identidad no podía evaluarse solo por conteo

V5 podía estimar un número razonable de voces pero reutilizar una misma etiqueta para voces acústicamente incompatibles. V5.1 añade embeddings por turno y prototipos por identidad.

Medidas de seguridad:

- un turno breve no se fusiona solo por duración;
- turnos largos no forman prototipos, porque pueden contener más de una voz;
- la reasignación exige coincidencia suficiente con otra identidad y margen frente a rivales;
- el escaneo local exige cambios sostenidos y está acotado para no repetir una diarización completa;
- en modo manual se mide consistencia pero no se altera automáticamente el número solicitado.

### A2. [CORREGIDO] Prototipo contaminado por turno largo

Durante la calibración se detectó que un turno largo con varias voces podía contaminar su propio prototipo y provocar reasignaciones inversas. Se corrigió excluyendo esos turnos de los prototipos y tratándolos solo como candidatos a escaneo local.

### A3. [LIMITACIÓN DOCUMENTADA] Ground truth

El número Auto es una estimación acústica. V5.1 no denomina ground truth a resultados automáticos. Los documentos marcan confianza estructural/de identidad y si existe o no ground truth externo.

### A4. [LIMITACIÓN DOCUMENTADA] Confianza nativa de sherpa 1.13.7

La versión Python utilizada por VtT no expone `confidence` en `OfflineSpeakerDiarizationSegment`; por tanto no se inventa una métrica sherpa inexistente. La confianza V5.1 es una evaluación propia de consistencia de embeddings.

### A5. [LIMITACIÓN DOCUMENTADA] Timers internos sherpa en Windows

La captura de `stderr` nativo no es fiable en todos los entornos Windows. VtT conserva siempre medición wall de `process()` y de cada pasada; cuando los timers internos se capturan, agrega segmentación/embeddings/clustering.

### A6. [PENDIENTE DE PRODUCTO] Android: audio largo completo en memoria

`AudioDecoder.decode()` sigue construyendo el PCM completo y luego un `FloatArray` mono 16 kHz. Para archivos de varias horas existe riesgo de OOM. Actualmente:

- se avisa para audio >90 min;
- se captura `OutOfMemoryError` con un mensaje accionable.

Solución de fondo pendiente: decodificación/transcripción por bloques con solape y deduplicación temporal. No se implementó en esta auditoría porque cambia la semántica de timestamps/contexto y requiere pruebas en dispositivo físico.

### A7. [CORREGIDO] whisper.cpp fijado por tag móvil

CMake ya no obtiene whisper.cpp mediante el tag móvil `v1.7.4`. Se fijó al commit exacto `8a9ad7844d6e2a10cddf4b92de4089d7ac2b14a9`; Android CI confirmó que el pin compila.

### A8. [HARDENING PENDIENTE] GitHub Actions por tags mayores

Los workflows siguen usando referencias como `actions/checkout@v4`. El endurecimiento completo requeriría fijar cada Action al SHA correspondiente y mantener esos SHA mediante un proceso de actualización. No se mezcló este cambio con la auditoría funcional sin una matriz de versiones verificada.

### A9. [LIMITACIÓN DE INTEGRIDAD] Primera descarga de modelos

- Escritorio diarización: los assets históricos consultados no entregan un digest de origen utilizable; se verifica HTTPS+tamaño y luego se fija hash local.
- Android Whisper: se calcula hash local después de la primera descarga, pero no existe todavía un catálogo interno de hashes esperados de origen.

La protección actual detecta corrupción posterior, no un servidor/origen comprometido durante la primera recepción.

### A10. [DEUDA TÉCNICA MENOR] Handle JNI deliberadamente no liberado

`nativeFree` libera `whisper_context` pero conserva el pequeño `Handle` para evitar una carrera con `nativeRequestAbort`. El costo es una fuga de pocos bytes por handle/modelo cargado durante la vida del proceso. No afecta el modelo pesado; debe revisarse si se rediseña la sincronización JNI.

## 4. Rendimiento y diarización

Las pruebas reales mostraron que la diarización puede dominar el tiempo en CPU, especialmente con `Precisa` (`window_shift_ratio=0.10`) y una segunda pasada Auto.

Recomendación operativa:

- uso normal: **Equilibrada (0.20)**;
- Precisa: solo cuando la resolución temporal justifique el costo;
- medir ASR y diarización por separado en cada equipo.

La calibración V5.1 con audios oficiales de sherpa de 2 y 4 hablantes observó, en esas muestras, pares de un mismo hablante hasta aproximadamente 0,45 y pares distintos hasta aproximadamente 0,33. Son referencias de ingeniería con márgenes conservadores, no biometría universal.

## 5. Verificación de cierre — COMPROBADA

### Desktop checks

`Desktop checks #41`, commit de documentación V5.1 `7ef467d8093830627f7c08edcfdc62decb6c39d2`: **success**. Compilación y pytest terminaron correctamente en Windows, macOS y Ubuntu. El código V5.1 ya había pasado además la ejecución #40 inmediatamente anterior.

### Smoke acústico V5.1

Workflow temporal ejecutado y luego eliminado. Resultado: **success**.

- `1-two-speakers-en.wav`: esperado 2, detectado **2**, 1 pasada, consistencia de identidad `media`.
- `0-four-speakers-zh.wav`: esperado 4, detectado **4**, 1 pasada, consistencia `alta`.
- En el segundo trabajo se comprobaron reutilización de modelos, motor y extractor de identidad.
- La capa V5.1 no alteró los conteos correctos.
- Tiempos wall sherpa del runner: aproximadamente 0,81 s y 4,62 s.

Estos audios validan un smoke de conteo/reutilización, no constituyen un benchmark completo de DER/JER.

### Android APK

`Android APK #19`, commit `2a4e186340c11db4642fa5a199554d82c152dbe8`: **success**.

- build debug: success;
- pin exacto de whisper.cpp: compilado;
- artefacto `TranscriptorVtT-debug-apk`: 5.875.573 bytes;
- digest del artefacto GitHub: `sha256:05dbc20ea1efb6617d919a9c7bd2445dec4c2a554679663c895ced251b09ee22`;
- release firmado opcional: omitido porque no había keystore configurado, sin convertirlo en falla.

### PyInstaller V5.1

`Desktop executables #6`, run `34379042391`: **success** en los tres sistemas.

- Windows: 126.819.307 bytes; `sha256:e354becf89500db02c4872ba80167ae6e2a6713b692f00628c103f82c19c1399`.
- Ubuntu: 186.146.208 bytes; `sha256:20d4e7dafecd2c66e5a71d248b092797b853f2bb87230eac74afe5b12f62a46f`.
- macOS: 198.704.500 bytes; `sha256:c1bf9ba76d03b6462e6a1749b2a1b90eeb058400dd7c880248559a5fe5848218`.

Los artefactos se construyeron desde `8acfa166094787bb74ea31ec0bafd49ebffa9f95` y expiran el 8 de diciembre de 2026.

### Limpieza

- workflow acústico temporal: **eliminado**;
- trigger temporal de `desktop-build.yml`: **restaurado** al blob manual original `b3e0ce08efc1def0294c9bf9c1181f0052ce6f25`;
- no hay diferencias permanentes en `desktop-build.yml` respecto de la base V5.1.

## 6. Qué NO queda probado por CI

- calidad acústica exacta en cada audio del usuario;
- funcionamiento de micrófono/loopback en cada hardware;
- memoria/batería/temperatura Android con audios largos;
- ground truth de hablantes en material no anotado;
- autenticación criptográfica de la primera descarga de modelos sin un digest oficial esperado.

Esas materias permanecen en `PRUEBAS_MANUALES.md` o en el roadmap y no impiden declarar cerrada la auditoría de código/CI/empaquetado V5.1.

## 7. Resultado de cierre

La auditoría V5.1 queda **cerrada para código, documentación, CI, smoke acústico reproducible y empaquetado**. Los pendientes que sobreviven son de producto/hardening y están expresamente documentados: audio largo Android por bloques, pins SHA de Actions, autenticación inicial de modelos y mejora futura de la sincronización/vida del pequeño Handle JNI.
