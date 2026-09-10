# PLAN MAESTRO — VtT

**Actualizado:** 9 de septiembre de 2026  
**Rama de trabajo:** `claude/voice-transcriber-multiplatform-6xifq1`  
**Estado:** **V5.2-performance — CIERRE TÉCNICO Y DOCUMENTAL VERIFICADO**

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
- alineación palabra↔hablante y división interna de segmentos.
- conteos sherpa / identidad / texto separados.
- contabilidad de identidad separa etapa final, evaluaciones ligeras y total acumulado.
- JSON schema v7 y DOCX diagnóstico V5.2 coherente con la versión efectiva.
- modelos sherpa con tamaño y SHA-256 auditado fijado en código.
- `Desktop checks #73` y `Desktop executables #9` verdes en Windows/macOS/Ubuntu.

### Android

- Kotlin + whisper.cpp/JNI, minSdk 24, ARM64.
- `TranscribeViewModel`, progreso/cancelación nativa, ACTION_SEND/ACTION_VIEW.
- TXT/SRT y persistencia del último documento.
- GGML tiny/base/small con hash esperado antes de aceptar la primera descarga.
- audios >5 min por bloques de 90 s con 2 s de solapamiento.
- handles JNI opacos/liberables con shared_ptr/mutex.
- whisper.cpp fijado a commit exacto.
- `Android APK #28` verde.
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
11. Un reporte generado por V5.2 no debe exponer rótulos V5.1 salvo contexto histórico explícito.
12. Cambios solo documentales no deben disparar matrices pesadas cuando pueden excluirse de forma segura.

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
- contabilidad completa de tiempo de identidad, incluidas evaluaciones ligeras;
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

### F7 — Coherencia documental y de reporting

Cerrado:

- README raíz y guía de escritorio actualizados a la arquitectura efectiva V5.2;
- mapa documental explícito;
- módulos V4/V5/V5.1 descritos como cadena de herencia/compatibilidad;
- `vtt_diarization_v52_metrics.py` y servicio V5.2 incorporados a la documentación técnica;
- DOCX nuevo renombra `Control identidad V5.1` a `Control identidad V5.2`;
- DOCX expone wall total/final/ligero de identidad;
- regresión automática del reporte Word;
- firma Android reclasificada como pendiente externo, no conflicto de código;
- cambios Markdown excluidos de las matrices pesadas de escritorio/Android, manteniendo los workflows como triggers de su propia validación.

## 5. Verificación de cierre

### Desktop checks

`Desktop checks #73`, run `34424880813`, sobre `7905071096f0bb0478aa07d6b419546a57cb11b7`: Windows/macOS/Ubuntu **success**. Incluye las regresiones V5.2, el DOCX actualizado y la configuración de filtro documental del workflow.

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

`Android APK #28`, run `34424903439`, sobre `5f51ae8c197cbd7ec8a72eb8e9c93e1532b2713a`: build debug, artefacto y release rodante **success**. Firma opcional no ejecutada por ausencia de keystore.

### PyInstaller V5.2

`Desktop executables #9`, run `34425016894`, commit `2156cae37ca2ecbaec5c57081d6f6c3409086e10`: Windows/macOS/Ubuntu **success**.

El trigger temporal se retiró y `desktop-build.yml` volvió al blob permanente `93d5121a6ec87c3fa05a9fff238749a567e479dc`, con `workflow_dispatch` como único disparador.

## 6. Pendientes sin necesidad de modificar código ahora

No queda una tarea técnica o documental de V5.2 que pueda cerrarse únicamente con más revisión estática/CI sin cambiar el objetivo del producto.

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
