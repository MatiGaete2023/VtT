# PLAN MAESTRO — VtT

**Actualizado:** 9 de septiembre de 2026  
**Rama de trabajo:** `claude/voice-transcriber-multiplatform-6xifq1`  
**Estado V5.1:** **CIERRE VERIFICADO**

Este documento describe el estado real posterior a la auditoría V5.1. Los defectos históricos ya resueltos no se mantienen como pendientes.

## 1. Objetivo del producto

VtT debe ofrecer transcripción local y privada, con instalación razonablemente simple, en:

- escritorio Windows/macOS/Linux;
- Android ARM64.

La red se usa únicamente para instalar dependencias, descargar modelos, descargar contenido mediante una acción explícita de YouTube y ejecutar CI/build. No se incorpora telemetría.

## 2. Estado actual

### Escritorio V5.1

- Python 3.9+.
- Entry point: `desktop/vtt_main.py`.
- ASR: faster-whisper/CTranslate2.
- Diarización: sherpa-onnx.
- perfiles ASR y perfiles de diarización independientes;
- Auto estructural con reintento condicionado;
- worker persistente;
- alineación palabra↔hablante;
- división interna de segmentos por cambio de voz;
- verificación V5.1 de identidad mediante embeddings y prototipos conservadores;
- escaneo local acotado de turnos largos;
- confianza de identidad y del conteo;
- JSON schema v6;
- DOCX diagnóstico;
- CI y PyInstaller verificados en Windows/macOS/Ubuntu.

### Android

- Kotlin + whisper.cpp/JNI;
- `TranscribeViewModel` para ciclo de vida;
- progreso/cancelación nativa;
- audio/video compartido;
- TXT/SRT;
- descarga reanudable de modelos;
- integridad local por tamaño + SHA-256 post-descarga;
- whisper.cpp fijado al commit `8a9ad7844d6e2a10cddf4b92de4089d7ac2b14a9`;
- APK debug CI verificado;
- sin diarización V5.1.

## 3. Reglas transversales

1. Audio del usuario procesado localmente.
2. Sin telemetría ni analytics.
3. Escritorio: Python mínimo 3.9; Android: minSdk 24/ARM64 salvo decisión expresa.
4. Sin exigir permisos de administrador para el flujo normal de Windows.
5. No perder ni sobrescribir silenciosamente el trabajo del usuario.
6. Documentación, mensajes de UI y commits del proyecto en español.
7. No afirmar como verificado algo que solo es estimado.
8. Antes de usar una API externa, comprobar su firma/versión real.
9. Código modular de escritorio: las nuevas responsabilidades deben permanecer en capas específicas.
10. Todo cambio funcional debe tener verificación prevista y posterior.

## 4. Fases cerradas

### F1 — Robustez de escritorio

Cerrado:

- loopback Windows mediante soundcard;
- grabaciones/transcripciones persistentes;
- actualización de venv por hash de requirements;
- instalación asíncrona de componentes de grabación;
- cierre seguro del WAV;
- salidas no destructivas;
- validación de pista de audio;
- lotes con éxito parcial;
- cancelación con salida parcial cuando hay material.

### F2 — Pipeline mejorado

Cerrado:

- perfiles ASR;
- batching/backends medidos;
- bloques legibles;
- DOCX;
- JSON detallado;
- glosario/hotwords;
- revisión sincronizada.

### F3 — Diarización V4/V5

Cerrado:

- perfiles Rápida/Equilibrada/Precisa;
- Auto estructural;
- progreso y ETA de diarización;
- worker persistente;
- instrumentación wall e interna cuando está disponible;
- alineación por palabra y división por cambio de voz.

### F4 — Identidad V5.1

Cerrado:

- prototipos acústicos por identidad;
- protección de microintervenciones;
- exclusión de turnos largos de prototipos;
- reasignación solo con evidencia acústica y margen;
- escaneo local acotado;
- confianza por identidad;
- Auto presentado como estimación, no ground truth;
- JSON schema v6.

## 5. Cierre V5.1 — EJECUTADO

### C1. Documentación coherente — OK

Actualizados `README.md`, `desktop/README.md`, `AUDITORIA.md`, `PLAN_MAESTRO.md`, `PRUEBAS_MANUALES.md`, `AGENTS.md`, `MODEL_CATALOG.md` y `android/README.md`.

Ya no se describe Python 3.8, JSON v2 ni una arquitectura monolítica como estado actual.

### C2. Auditoría Android/workflows — OK con límites documentados

Comprobados ciclo de vida, cancelación, descarga/integridad de modelos, manifest/intents, Gradle, CMake/JNI y workflows. Cambios permanentes:

- pin exacto de whisper.cpp;
- permisos GitHub Actions reducidos por job;
- limpieza del keystore temporal.

Límite de producto que continúa: audio Android completo en memoria para transcribir; requiere una fase específica por bloques y pruebas físicas.

### C3. Smoke acústico V5.1 — OK

Audios oficiales sherpa-onnx:

- 2 hablantes → 2 detectados, identidad media;
- 4 hablantes → 4 detectados, identidad alta;
- 1 pasada en ambos;
- reutilización de modelos, motor y extractor comprobada en el segundo archivo.

El workflow temporal usado para esta prueba fue eliminado después.

### C4. PyInstaller V5.1 — OK

`Desktop executables #6` completó exitosamente Windows/macOS/Ubuntu y produjo artefactos para los tres sistemas.

### C5. Limpieza — OK

- smoke workflow temporal eliminado;
- `desktop-build.yml` restaurado a `workflow_dispatch` manual y al blob original;
- comparación final no muestra diferencias netas del trigger temporal.

## 6. Roadmap posterior

### P1 — Android: audio largo por bloques

Problema real abierto: `AudioDecoder` conserva PCM completo en memoria. Diseñar decodificación incremental y transcripción por bloques con solape. Debe resolver:

- continuidad de timestamps;
- deduplicación del solape;
- cancelación;
- memoria acotada;
- persistencia parcial.

No implementar sin pruebas en dispositivo físico.

### P2 — Supply-chain hardening

- fijar GitHub Actions por SHA tras comprobar cada acción;
- evaluar lockfile/hash de dependencias Python para builds reproducibles;
- completar un catálogo de hashes esperados de modelos cuando exista una fuente confiable.

No inventar digests.

### P2 — Métricas de calidad de diarización

Construir un corpus pequeño con ground truth manual de hablantes y cambios. Medir DER/JER o, como mínimo, precisión de boundaries y consistencia de identidad. Los audios oficiales de 2/4 hablantes son smoke tests, no benchmark suficiente.

### P3 — Android y diarización

No trasladar sherpa/V5.1 al APK hasta resolver costo, tamaño de modelos, memoria y UX. Android mantiene ASR local sin diarización por diseño actual.

### P3 — Handle JNI

Evaluar una sincronización que permita liberar también el pequeño `Handle` nativo sin riesgo de carrera con `nativeRequestAbort`. La fuga actual es deliberada y de pocos bytes por handle, no del modelo pesado.

## 7. Configuración recomendada para uso real

### Escritorio general

- modelo: `small` o `medium` según hardware/precisión;
- ASR: Equilibrado;
- diarización: Equilibrada;
- Auto cuando no se conoce el número de voces;
- Precisa solo cuando el costo CPU sea aceptable.

### Evaluación de un problema

Comparar en el mismo audio:

1. ASR seconds;
2. diarization seconds;
3. wall por cada pasada;
4. número estimado de voces;
5. confianza de identidad;
6. segmentos divididos/cambios internos;
7. revisión humana de boundaries seleccionados.

## 8. Criterio de una tarea “terminada”

Una tarea solo se cierra cuando:

- el código está publicado;
- la verificación prevista se ejecutó;
- CI relevante está verde;
- se documentaron limitaciones;
- no quedaron archivos/workflows temporales;
- el resultado no depende de una afirmación no comprobada.

Si un mismo fallo se repite 5–10 veces sin una estrategia nueva, detener los reintentos, documentar causa/estado y continuar con el siguiente problema.
