# PLAN MAESTRO — VtT

**Actualizado:** 9 de septiembre de 2026  
**Rama de trabajo:** `claude/voice-transcriber-multiplatform-6xifq1`  
**Estado:** **V5.2-performance — CIERRE TÉCNICO VERIFICADO**

## 1. Objetivo

VtT ofrece transcripción local y privada en escritorio Windows/macOS/Linux y Android ARM64. La red se limita a dependencias, modelos, descarga explícita de YouTube y CI/build. No hay telemetría.

## 2. Estado actual

### Escritorio V5.2

- Python 3.9+; entrypoint `desktop/vtt_main.py`.
- faster-whisper/CTranslate2.
- sherpa-onnx con perfiles Rápida/Equilibrada/Precisa.
- modos globales Rápido/Equilibrado/Preciso/Personalizado.
- migración conservadora de configuraciones anteriores.
- Auto estructural + precheck acústico presupuestado + selección identity-aware.
- worker persistente y reutilización de PCM/embeddings.
- sonda de turnos largos antes del escaneo detallado.
- conteos sherpa / identidad / texto separados.
- JSON schema v7 y DOCX diagnóstico.
- modelos sherpa con tamaño y SHA-256 auditado fijado en código.
- Desktop checks y PyInstaller V5.2 verdes en Windows/macOS/Ubuntu.

### Android

- Kotlin + whisper.cpp/JNI, minSdk 24, ARM64.
- `TranscribeViewModel`, progreso/cancelación nativa, ACTION_SEND/ACTION_VIEW.
- TXT/SRT y persistencia del último documento.
- GGML tiny/base/small con hash esperado antes de aceptar la primera descarga.
- audios >5 min por bloques de 90 s con 2 s de solapamiento.
- handles JNI opacos/liberables con shared_ptr/mutex.
- whisper.cpp fijado a commit exacto.
- Android APK final verde.
- sin diarización por diseño actual.

## 3. Reglas transversales

1. Audio procesado localmente.
2. Sin telemetría.
3. Windows normal sin privilegios de administrador.
4. No perder ni sobrescribir silenciosamente trabajo.
5. No presentar estimaciones como ground truth.
6. Verificar APIs/dependencias contra la versión realmente utilizada.
7. Distinguir pin auditado de firma publicada por upstream.
8. Mantener modularidad de escritorio.
9. Todo cambio funcional debe tener verificación prevista y posterior.
10. Retirar infraestructura temporal tras recopilar evidencia.

## 4. Fases cerradas

### F1 — Robustez escritorio

Loopback Windows, persistencia, venv por hash, instalaciones asíncronas, WAV seguro, salidas no destructivas, validación de pista, lotes y cancelación parcial.

### F2 — Pipeline mejorado

Perfiles ASR, batching/backends, bloques legibles, DOCX/JSON, glosario y revisión sincronizada.

### F3 — Diarización V4/V5

Perfiles, Auto estructural, progreso, worker persistente, timers y alineación palabra↔hablante.

### F4 — Identidad V5.1

Prototipos conservadores, protección de microintervenciones, escaneo local, confianza y Auto como estimación.

### F5 — V5.2-performance

Cerrado:

- precheck antes de segunda pasada completa cuando es seguro;
- selección identity-aware;
- identidad rival-aware para dos apariciones;
- sonda barata para turnos largos;
- reutilización PCM/embeddings;
- conteos separados;
- JSON schema v7;
- modos globales/presupuesto de rendimiento;
- benchmark ASR reproducible;
- pins auditados sherpa;
- migración de perfiles sin sobrescribir preferencias.

### F6 — Hardening Android

Cerrado:

- SHA-256 esperado de GGML;
- bloques largos;
- handle JNI sin fuga deliberada;
- Actions fijadas por SHA.

## 5. Verificación de cierre

### Desktop checks

`Desktop checks #65` sobre `d5d100e0c2a6f14c809ad022f84a6d1fd750ab64`: Windows/macOS/Ubuntu **success**.

### Smoke V5.2

Audios oficiales sherpa:

- 2 hablantes → 2;
- 4 hablantes → 4;
- una pasada en ambos;
- reutilización de modelos, motor y extractor.

Workflow temporal eliminado.

### Hashes sherpa

Dos descargas independientes reprodujeron archive/embedding; se auditó el ONNX extraído. Valores fijados y con pruebas de regresión.

### Benchmark ASR público

Las cuatro combinaciones de `benchmark_asr.py` ejecutaron sobre `jfk.flac`. No es benchmark de español ni del audio del usuario.

### Android

`Android APK #26` sobre `1f6bf9ea8cbca01cc19264dabd2718e49f85e311`: build debug, artefacto y release rodante **success**. Firma opcional no ejecutada por ausencia de keystore.

### PyInstaller V5.2

`Desktop executables #7`, run `34406483435`, commit `9e6ec19bd6216362b5527ca2c00305d0c61cdfe4`: Windows/macOS/Ubuntu **success**.

El trigger temporal se retiró y `desktop-build.yml` volvió a `workflow_dispatch` únicamente.

## 6. Pendientes sin necesidad de modificar código ahora

No queda una tarea técnica de la fase V5.2 que pueda cerrarse únicamente con más revisión estática/CI sin cambiar el objetivo del producto.

La reproducibilidad Python con lock/hashes transitivos sigue siendo una posible mejora futura: requiere diseñar una matriz de wheels por SO/arquitectura y una política de actualización, no simplemente congelar el entorno de un único runner.

## 7. Próximas validaciones externas

### R1 — Audio real V5.2

Repetir un audio problemático conocido y comparar ASR, diarización, precheck, pasadas, clusters por etapa y calidad humana de las etiquetas. No prometer real-time hasta medirlo en el hardware objetivo.

### R2 — Corpus anotado

Crear corpus pequeño con ground truth temporal y medir DER/JER o métricas equivalentes.

### R3 — Hardware

- micrófono/loopback por SO;
- CUDA;
- apertura de binarios PyInstaller;
- Android físico: bloques largos, memoria, batería, temperatura, cancelación y actualización firmada.

### R4 — Android diarización

No trasladar sherpa/V5.2 al APK sin evaluar tamaño, memoria, rendimiento y UX. Android permanece ASR-only.

## 8. Configuración recomendada

Uso general: modo global **Equilibrado**. Configuraciones antiguas/específicas que no coincidan con un preset permanecen **Personalizado**. Preciso solo cuando su costo tenga justificación.

## 9. Criterio de tarea terminada

Una tarea se cierra cuando hay código publicado, verificación ejecutada, CI/build verde, límites documentados, ausencia de infraestructura temporal y ninguna afirmación depende de evidencia inexistente.

Ante dos fallos de la misma causa, cambiar de estrategia.
