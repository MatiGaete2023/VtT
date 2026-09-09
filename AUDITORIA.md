# AUDITORÍA DEL REPOSITORIO — VtT

**Actualizada:** 9 de septiembre de 2026  
**Rama auditada:** `claude/voice-transcriber-multiplatform-6xifq1`  
**Base funcional V5.1 al iniciar esta revisión:** `aa1b8d8b5407869d55225c46bf3b199d00b72e3d`

Este documento sustituye la auditoría antigua de julio, cuyos hallazgos mezclaban defectos ya corregidos con pendientes todavía vigentes. Solo se mantienen como abiertos los puntos que siguen presentes en el código actual.

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
- PyInstaller: workflow manual en los tres sistemas.

### Android

Estado: **funcional para ASR local; no tiene diarización V5.1**.

- Kotlin + whisper.cpp/JNI.
- `minSdk 24`, ARM64.
- Progreso y cancelación nativa.
- El trabajo vive en `TranscribeViewModel`; `Transcriber` sincroniza carga/transcripción/liberación.
- Admite ACTION_SEND/ACTION_VIEW para audio y video.
- TXT/SRT, persistencia del último documento y texto editado separado del original.
- Descargas de modelo reanudables y protección de integridad local por tamaño + SHA-256 calculado tras la descarga.

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

## 3. Hallazgos de la revisión V5.1

### A1. [CORREGIDO EN V5.1] Identidad de hablantes no podía evaluarse solo por conteo

V5 podía estimar un número razonable de voces pero reutilizar una misma etiqueta para voces acústicamente incompatibles. V5.1 añade embeddings por turno y prototipos por identidad.

Medidas de seguridad del algoritmo:

- un turno breve no se fusiona solo por duración;
- turnos largos no forman prototipos, porque pueden contener más de una voz;
- la reasignación exige coincidencia suficiente con otra identidad y margen frente a rivales;
- el escaneo local exige cambios sostenidos y está acotado para no repetir una diarización completa;
- en modo manual se mide consistencia pero no se altera automáticamente el número solicitado.

### A2. [CORREGIDO EN V5.1] Riesgo de prototipo contaminado por turno largo

Durante la calibración inicial se detectó que un turno largo con varias voces podía contaminar su propio prototipo y provocar reasignaciones inversas. Se corrigió excluyendo esos turnos de la construcción de prototipos y tratándolos solo como candidatos a escaneo local.

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

Solución de fondo pendiente: decodificación/transcripción por bloques con solape y deduplicación temporal. No se implementa sin una prueba real en dispositivo, porque cambia la semántica de timestamps y el uso del contexto Whisper.

### A7. [SEGURIDAD/MANTENIBILIDAD] whisper.cpp fijado por tag móvil

`android/app/src/main/cpp/CMakeLists.txt` usa `GIT_TAG v1.7.4`. El tag oficial resuelve actualmente al commit `8a9ad7844d6e2a10cddf4b92de4089d7ac2b14a9`. Debe fijarse a ese commit para reproducibilidad del build.

### A8. [SEGURIDAD/MANTENIBILIDAD] GitHub Actions por tags mayores

Los workflows usan referencias como `actions/checkout@v4`. Es práctica común, pero no es un pin criptográfico. El endurecimiento completo requeriría fijar cada Action al SHA correspondiente y mantener esos SHA mediante un proceso de actualización. Se documenta como hardening; no debe mezclarse con cambios funcionales sin comprobar todos los SHA.

### A9. [LIMITACIÓN DE INTEGRIDAD] Primera descarga de modelos

- Escritorio diarización: los assets históricos consultados no entregan un digest de origen utilizable; se verifica HTTPS+tamaño y luego se fija hash local.
- Android Whisper: se calcula hash local después de la primera descarga, pero no existe todavía un catálogo interno de hashes esperados de origen.

La protección actual detecta corrupción posterior, no un servidor/origen comprometido en la primera descarga.

### A10. [DEUDA TÉCNICA MENOR] Handle JNI deliberadamente no liberado

`nativeFree` libera `whisper_context` pero conserva el pequeño `Handle` para evitar una carrera con `nativeRequestAbort`. El costo es una fuga de pocos bytes por handle/modelo cargado durante la vida del proceso. No afecta el audio/modelo pesado, pero debe revisarse si se rediseña la sincronización JNI.

## 4. Rendimiento y diarización

Las pruebas reales mostraron que el costo de diarización puede dominar el procesamiento en CPU, especialmente con perfil `Precisa` (`window_shift_ratio=0.10`) y una segunda pasada Auto.

Recomendación operativa:

- uso normal: **Equilibrada (0.20)**;
- Precisa: solo cuando la resolución temporal justifique el costo;
- medir ASR y diarización por separado en cada equipo.

La calibración V5.1 con audios oficiales de sherpa de 2 y 4 hablantes observó, en esa muestra, pares de un mismo hablante hasta aproximadamente 0,45 y pares distintos hasta aproximadamente 0,33. Esos valores se usan como referencia de ingeniería con márgenes conservadores, no como biometría universal.

## 5. CI y empaquetado

### Desktop checks

Debe compilar el entrypoint y todos los módulos V5.1 y ejecutar toda la suite `desktop/tests` en:

- Windows;
- macOS;
- Ubuntu.

### Desktop executables

PyInstaller recopila explícitamente faster-whisper, CTranslate2, onnxruntime, sherpa-onnx, PyAV, tokenizers, python-docx, sounddevice, soundcard, numpy y CFFI.

### Android APK

Compila debug en Ubuntu y publica el artefacto. Existe un build release firmado opcional si el repositorio tiene secrets de keystore.

## 6. Qué NO está afirmado

- Android no tiene diarización V5.1.
- Auto no determina con certeza el número real de personas.
- Una etiqueta `Persona N` no identifica biométricamente a una persona.
- La CI no demuestra calidad acústica en el PC del usuario.
- Un build exitoso no demuestra que micrófono/loopback funcionen en cada hardware.
- Los hashes locales no autentican la primera descarga si no existe un digest esperado de una fuente independiente.

## 7. Criterio de cierre de esta auditoría

La revisión se considera cerrada cuando:

1. documentación y código describen la misma arquitectura;
2. los tests V5.1 pasan en los tres SO;
3. se ejecuta un smoke acústico end-to-end con audios de 2 y 4 hablantes conocidos;
4. PyInstaller V5.1 termina en Windows/macOS/Linux;
5. cualquier workflow temporal usado para pruebas se elimina;
6. Android queda compilando si se modifica su build nativo;
7. el árbol final se compara contra el commit funcional validado y se explican solo las diferencias permanentes.
