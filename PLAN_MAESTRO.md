# PLAN MAESTRO — VtT

**Actualizado:** 9 de septiembre de 2026  
**Rama de trabajo:** `claude/voice-transcriber-multiplatform-6xifq1`  
**Estado:** V5.2-performance en cierre de verificación

## 1. Objetivo

VtT debe ofrecer transcripción local y privada con una instalación simple en escritorio Windows/macOS/Linux y Android ARM64. La red se limita a dependencias, modelos, descarga explícita de YouTube y CI/build. No hay telemetría.

## 2. Estado actual

### Escritorio V5.2

- Python 3.9+; entrypoint `desktop/vtt_main.py`.
- faster-whisper/CTranslate2.
- sherpa-onnx con perfiles de diarización.
- modos globales Rápido/Equilibrado/Preciso/Personalizado.
- migración conservadora de configuraciones anteriores.
- Auto estructural + precheck acústico presupuestado + selección identity-aware.
- worker persistente y reutilización de PCM/embeddings.
- sonda de turnos largos antes del escaneo detallado.
- conteos sherpa / identidad / texto separados.
- JSON schema v7 y DOCX diagnóstico.
- modelos sherpa con tamaño y SHA-256 auditado fijado en código.

### Android

- Kotlin + whisper.cpp/JNI, minSdk 24, ARM64.
- `TranscribeViewModel`, progreso/cancelación nativa, ACTION_SEND/ACTION_VIEW.
- TXT/SRT y persistencia del último documento.
- GGML tiny/base/small con hash esperado antes de aceptar la primera descarga.
- audios >5 min por bloques de 90 s con 2 s de solapamiento.
- handles JNI opacos y liberables con shared_ptr/mutex.
- whisper.cpp fijado a commit exacto.
- sin diarización por diseño actual.

## 3. Reglas transversales

1. Audio procesado localmente.
2. Sin telemetría.
3. Windows normal sin privilegios de administrador.
4. No perder ni sobrescribir silenciosamente trabajo.
5. No presentar estimaciones como ground truth.
6. APIs y dependencias externas deben verificarse contra la versión realmente utilizada.
7. No inventar digests; distinguir pin auditado de firma publicada por upstream.
8. Nuevas responsabilidades de escritorio deben vivir en módulos específicos.
9. Todo cambio funcional debe tener prueba prevista y posterior.
10. Infraestructura temporal de verificación debe retirarse tras usarse.

## 4. Fases cerradas

### F1 — Robustez de escritorio

Cerrado: loopback Windows, persistencia, venv por hash, instalaciones asíncronas, WAV seguro, salidas no destructivas, validación de pista de audio, lotes y cancelación parcial.

### F2 — Pipeline mejorado

Cerrado: perfiles ASR, batching/backends, bloques legibles, DOCX/JSON, glosario, revisión sincronizada.

### F3 — Diarización V4/V5

Cerrado: perfiles, Auto estructural, progreso, worker persistente, timers y alineación palabra↔hablante.

### F4 — Identidad V5.1

Cerrado: prototipos conservadores, protección de microintervenciones, escaneo local, confianza y tratamiento de Auto como estimación.

### F5 — V5.2-performance

Implementado:

- precheck de identidad antes de una segunda pasada completa en casos compatibles;
- selección identity-aware entre candidatos ambiguos;
- control rival-aware de identidades con dos apariciones;
- sonda barata para turnos largos;
- reutilización de PCM/embeddings;
- conteos separados por etapa;
- JSON schema v7;
- modos globales y presupuesto de tiempo real;
- benchmark ASR reproducible;
- pins auditados de modelos sherpa;
- migración de perfiles sin sobrescribir preferencias antiguas.

### F6 — Hardening Android

Implementado:

- SHA-256 esperado de GGML en primera descarga;
- bloques largos con decodificación temporal acotada;
- handle JNI sin fuga deliberada;
- Actions fijadas por SHA.

## 5. Verificación ya ejecutada

### Smoke acústico V5.2

Audios oficiales sherpa:

- 2 hablantes → 2;
- 4 hablantes → 4;
- una pasada en ambos;
- reutilización de modelos, motor y extractor comprobada.

El workflow temporal utilizado para la campaña fue eliminado.

### Hashes sherpa

Dos descargas independientes de assets oficiales produjeron los mismos hashes para archive y embedding; se obtuvo además el hash del ONNX extraído. Los valores están fijados en `vtt_diarization.py` y probados por regresión.

### Benchmark ASR público

`benchmark_asr.py` ejecutó las cuatro combinaciones previstas sobre `jfk.flac`. Sirve para verificar flujo y costo relativo en ese runner, no como benchmark de precisión del audio del usuario.

### Android

La implementación de bloques largos/JNI/model hashes compiló en el workflow Android. Debe volver a comprobarse el workflow final cuando termine la última actualización de Actions/documentación.

## 6. Pendientes que NO requieren audio del usuario

Antes del cierre final de esta rama:

1. CI desktop final verde con las últimas pruebas/documentación.
2. Android APK final verde con el workflow actualizado.
3. PyInstaller final Windows/macOS/Ubuntu.
4. confirmar ausencia de workflows/triggers temporales y coherencia del árbol/documentación.

## 7. Roadmap que sí requiere evaluación externa

### R1 — Calidad acústica real V5.2

Repetir un audio problemático conocido y comparar:

- ASR seconds;
- diarización total;
- precheck y si evita segunda pasada;
- número de clusters por etapa;
- confianza de identidad;
- revisión humana de cambios/etiquetas.

No prometer tiempo menor a real-time hasta medirlo en el hardware objetivo.

### R2 — Corpus anotado

Construir corpus pequeño con ground truth temporal y medir DER/JER o métricas equivalentes de boundaries/identidad.

### R3 — Hardware

- micrófono y loopback por SO;
- CUDA;
- Android físico: bloques largos, memoria, batería, temperatura, cancelación y actualización firmada.

### R4 — Android diarización

No trasladar sherpa/V5.2 al APK hasta evaluar tamaño, memoria, rendimiento y UX. Android permanece ASR-only.

### R5 — Reproducibilidad adicional

Evaluar lock/hashes de dependencias Python y una política de actualización periódica de Actions/model pins. No mezclar actualización automática con confianza implícita.

## 8. Configuración recomendada

Uso general: modo global **Equilibrado**. Si una configuración antigua o específica no coincide con un preset, conservar **Personalizado**. Usar Preciso solo cuando su costo tenga una justificación concreta.

## 9. Criterio de tarea terminada

Una tarea se cierra cuando:

- código publicado;
- verificación prevista ejecutada;
- CI/build relevante verde;
- límites documentados;
- sin infraestructura temporal;
- ninguna afirmación depende de un resultado no comprobado.

Ante dos fallos de la misma causa, cambiar de estrategia en lugar de repetir indefinidamente.
