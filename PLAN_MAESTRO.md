# PLAN MAESTRO — VtT

**Actualizado:** 13 de septiembre de 2026  
**Rama de trabajo:** `claude/voice-transcriber-multiplatform-6xifq1`  
**Estado:** **V5.2.1 — INTEGRACIÓN CORREGIDA; SIGUIENTE FASE = BENCHMARK INSTITUCIONAL CONTROLADO**

## 1. Objetivo

VtT ofrece transcripción local y privada en escritorio Windows/macOS/Linux y Android ARM64. La prioridad actual del escritorio es lograr un equilibrio práctico entre precisión de ASR, calidad de separación de voces y tiempo de proceso en CPU institucional, sin presentar Auto como ground truth.

## 2. Estado actual

### Escritorio V5.2.1

- Python 3.9+; entrypoint `desktop/vtt_main.py`.
- faster-whisper/CTranslate2 + sherpa-onnx.
- presets globales completos:
  - Rápido = `small / ASR Rápido / Auto / diarización Rápida 0.25`;
  - Equilibrado = `small / ASR Equilibrado / Auto / diarización Equilibrada 0.20`;
  - Preciso = `medium / ASR Preciso / Auto / diarización Equilibrada 0.20`;
  - Personalizado = controles libres, incluida Precisa 0.10.
- Auto estructural + precheck acústico + selección identity-aware.
- presupuesto temporal por preset antes de repetir una pasada Sherpa completa.
- worker persistente y reutilización de PCM/embeddings.
- alineación palabra↔hablante y división interna.
- conteos sherpa / identidad / texto separados y auditables.
- checkpoint ASR recuperable antes de diarización.
- cancelación compartida entre servicios V5/V5.1/V5.2.
- métricas finales con `processing_seconds`, `report_generation_seconds` y `end_to_end_seconds`.
- DOCX V5.2 directo de un solo guardado; JSON schema v8.
- hashes sherpa auditados y fijados.
- `Desktop checks #91`: 99 pruebas verdes en Windows/macOS/Ubuntu.

### Android

Sin cambios funcionales en V5.2.1:

- Kotlin + whisper.cpp/JNI, ARM64, minSdk 24;
- GGML tiny/base/small con hash esperado;
- audios largos por bloques 90 s + 2 s solapamiento;
- handles JNI opacos/shared_ptr;
- ASR-only por diseño actual.

## 3. Reglas transversales

1. Audio procesado localmente.
2. Sin telemetría.
3. Windows normal sin privilegios de administrador.
4. No perder ni sobrescribir trabajo reconocido.
5. No presentar estimaciones como ground truth.
6. Verificar APIs/dependencias contra la versión real.
7. Distinguir pin auditado de firma upstream.
8. Mantener modularidad y cadena de herencia V4/V5/V5.1/V5.2.
9. Todo cambio funcional debe tener prueba prevista y posterior.
10. Retirar workflows/triggers temporales después de recopilar evidencia.
11. No optimizar por intuición cuando existe un benchmark controlado posible.
12. Separar velocidad de procesamiento estable de espera extremo a extremo.

## 4. Fases cerradas

### F1 — Robustez escritorio

Loopback, persistencia, venv por hash, WAV seguro, salidas no destructivas, lotes y cancelación parcial.

### F2 — Pipeline mejorado

Perfiles ASR, batching/backends, bloques, DOCX/JSON, glosario y revisión.

### F3 — Diarización V4/V5

Perfiles, Auto estructural, worker persistente, timers y alineación por palabra.

### F4 — Identidad V5.1

Prototipos conservadores, microintervenciones, escaneo local y confianza.

### F5 — V5.2-performance

Precheck, selection identity-aware, identidad rival-aware, sonda larga, reutilización PCM/embeddings, conteos separados y hardening de modelos.

### F6 — Hardening Android

Hashes GGML, bloques largos, JNI seguro y Actions fijadas.

### F7 — Coherencia documental/reporting

Rótulos V5.2, métricas identidad completas, mapa documental y CI documental optimizada.

### F8 — V5.2.1 integración y presupuesto

Cerrado por código/CI:

- excepción única `DiarizacionCancelada`;
- ASR recuperable ante fallo/cancelación posterior;
- eliminación del overwrite `detected_speakers = len(speakers)`;
- conteos explícitos de sherpa, identidad auditada, texto y raw sin texto;
- performance recalculado desde tiempos finales;
- `end_to_end_seconds` separado de `processing_seconds`;
- DOCX directo con un solo `Document.save()`;
- presets globales activan Auto de forma inequívoca;
- Precisa 0.10 retirada de presets globales;
- presupuesto Auto proyecta el costo de la segunda pasada y puede omitirla con estado ambiguo;
- 99 pruebas automatizadas verdes en los tres SO.

## 5. Evidencia que motivó F8

### Prueba institucional Preciso

Audio ~404 s:

- ASR ~324 s;
- diarización ~785 s;
- Sherpa ~513 s;
- embeddings sherpa ~474 s;
- segunda pasada ~216 s.

Conclusión: diarización Precisa 0.10 no es una configuración operativa habitual en ese PC.

### Prueba institucional small/Equilibrado

Mismo audio:

- carga ~12 s;
- ASR ~164 s;
- procesamiento ~165 s;
- 2.45× tiempo real.

Pero diarización quedó desactivada por el bug de semántica del preset. Esa campaña solo valida velocidad ASR. F8 corrige el bug antes de repetir la medición.

## 6. Verificación automatizada actual

`Desktop checks #91`, run `34729633409`, commit `e35c1270b579964d4e9062dae929e7742c374c63`:

- Windows: success;
- Ubuntu: success;
- macOS: success;
- `py_compile`: success;
- `pytest`: **99 passed**.

El empaquetado V5.2.1 se ejecuta como `Desktop executables #10`; su resultado debe mantenerse en `AUDITORIA.md`/`PRUEBAS_MANUALES.md` una vez finalizado.

## 7. Próxima fase — R1 rendimiento institucional controlado

No añadir nuevas heurísticas antes de esta campaña.

### R1.1 — Equilibrado + Auto

Sobre el mismo audio y PC institucional:

- modo global **Equilibrado**;
- comprobar en UI antes de iniciar: `small`, ASR Equilibrado, `Hablantes Auto`, diarización Equilibrada 0.20;
- mantener Word + JSON;
- registrar carga, ASR, presupuesto de diarización, primera pasada, precheck, decisión de retry, wall sherpa, embeddings, identidad, reportes y end-to-end;
- revisar calidad humana de cortes de voz.

Meta orientativa: que la diarización quepa en el margen restante después del ASR (~235 s en la prueba previa). No es una promesa de tiempo real.

### R1.2 — Hilos 1/2/4

Solo si diarización sigue dominando, repetir una configuración idéntica variando `VTT_DIAR_THREADS` = 1, 2, 4. Más hilos no se asumirán más rápidos.

### R1.3 — Aislar precisión ASR

Si small/Equilibrado pierde demasiada precisión léxica, comparar después `medium + ASR Equilibrado` manteniendo la misma diarización. Cambiar un factor por vez.

## 8. Otras validaciones externas

- DER/JER con corpus anotado;
- micrófono/loopback por SO;
- CUDA;
- apertura/uso de binarios PyInstaller;
- Android físico: bloques largos, memoria, batería, temperatura y actualización firmada.

## 9. Criterio de tarea terminada

Una tarea se cierra cuando hay código publicado, pruebas/regresiones, CI/build aplicable, límites documentados, infraestructura temporal retirada y ninguna afirmación depende de evidencia inexistente.

Ante dos fallos de la misma causa, cambiar de estrategia.