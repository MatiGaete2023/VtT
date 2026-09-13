# AGENTS.md — Reglas del repositorio VtT

Contrato para cualquier persona o agente que modifique este repositorio.

## 1. Producto y plataformas

VtT tiene dos aplicaciones relacionadas pero no equivalentes:

- `desktop/`: Python/Tkinter, faster-whisper y diarización sherpa-onnx V5.2.1.
- `android/`: Kotlin + whisper.cpp/JNI. Android no incorpora diarización del escritorio.

## 2. Reglas inquebrantables

1. **Offline-first y privado.** El audio del usuario no se envía a servicios de transcripción.
2. **Sin telemetría.** No añadir analytics/tracking.
3. **Instalación simple.** Escritorio Python 3.9+; Android APK.
4. **Sin privilegios de administrador en Windows normal.** Documentar requisitos de sistema de Linux/macOS cuando existan.
5. **Nunca perder trabajo.** No sobrescribir silenciosamente grabaciones/exportaciones ni descartar ASR ya terminado porque falle una etapa posterior.
6. **No confundir estimación con certeza.** Auto y confianza acústica no son ground truth.
7. **Idioma del producto:** UI, mensajes y documentación en español.
8. **Compatibilidad:** escritorio Python ≥3.9; Android minSdk 24 y ARM64 salvo decisión expresa.
9. **No versionar** venv, modelos descargados, grabaciones, transcripciones, builds/APK o temporales.
10. **Verificar APIs externas** contra la versión realmente utilizada.
11. **No inventar hashes.** Distinguir un digest publicado por upstream de un pin auditado/reproducido por VtT.
12. **Supply chain:** workflows de CI/build deben preferir acciones fijadas por SHA y revisiones explícitas.
13. **Cambios con verificación.** Definir y ejecutar la comprobación antes de cerrar.
14. **Infraestructura temporal:** eliminar workflows/triggers temporales después de recopilar evidencia.
15. **Versionado visible coherente.** Un reporte generado por V5.2.1 no debe mostrar rótulos de versiones antiguas salvo contexto histórico explícito.
16. **Métricas honestas.** No conservar indicadores derivados calculados antes de conocer los tiempos finales.

## 3. Arquitectura de escritorio

Entry point final: `desktop/vtt_main.py`.

Capas actuales:

- `vtt_core.py`: estructuras, bloques y exportación base.
- `vtt_alignment.py`: alineación palabra↔hablante.
- `vtt_diarization_errors.py`: excepción `DiarizacionCancelada` compartida por todos los servicios persistentes.
- `vtt_diarization_v5.py`: motor persistente e instrumentación base; expone hooks y presupuesto temporal.
- `vtt_identity_v52.py`: identidad rival-aware y sonda de turnos largos.
- `vtt_diarization_v52.py`: precheck Auto, selección identity-aware, reutilización acústica y decisión de retry por presupuesto.
- `vtt_diarization_v52_metrics.py`: contabilidad completa de evaluaciones ligeras + etapa final de identidad.
- `vtt_diarization_service_v52.py`: worker persistente efectivo usado por el pipeline final.
- `vtt_validation_v52.py`: validación por etapa.
- `vtt_reporting_v52.py`: JSON schema v8 y DOCX diagnóstico directo.
- `vtt_performance.py`: presets globales completos, presupuesto temporal y estado de rendimiento.
- `vtt_pipeline_v52.py`: pipeline final y conteos explícitos.
- `vtt_ui_v52.py`: UI de presets completos y migración conservadora.

Los módulos `v4`, `v5` y `v51` permanecen porque V5.2.1 hereda de esas capas. No eliminarlos ni tratarlos como código muerto solo por el nombre de versión sin comprobar la cadena real de imports/MRO.

No volver a concentrar lógica nueva en `transcriptor_whisper.py` si puede vivir en una capa específica.

### Hilos y Tk

Los workers no modifican widgets directamente. Usar colas y `root.after`/mecanismos existentes. Mantener diarización fuera del hilo UI.

### Cancelación y conservación del trabajo

- Todos los servicios V5/V5.1/V5.2 deben importar **la misma** `DiarizacionCancelada` desde `vtt_diarization_errors.py`.
- El pipeline debe traducirla a `transcriptor_whisper.Cancelado`; no convertir una cancelación normal en `archivo_fallido`.
- Después de completar ASR y antes de una diarización costosa, mantener el checkpoint atómico `*_ASR_RECUPERABLE.json`.
- El checkpoint se elimina solo tras éxito completo. Ante fallo/cancelación posterior, se conserva.

### Diarización/identidad

- Equilibrada 0.20 es la recomendación general.
- Precisa 0.10 es opción avanzada/personalizada; no volver a incluirla en un preset global sin evidencia nueva.
- Una intervención breve no se fusiona solo por duración.
- Turnos largos no forman prototipos si pueden contener varias voces.
- El precheck V5.2 tiene presupuesto acotado; no debe transformarse en otra diarización completa.
- El presupuesto temporal puede **omitir una segunda pasada**, nunca la primera. Si lo hace, el resultado debe quedar explícitamente ambiguo/limitado por presupuesto.
- En modo manual N, no crear identidades adicionales automáticamente sin decisión explícita.
- No reemplazar nunca un conteo acústico por `len(speakers)` ni por el número de bloques/textos.
- Mantener separados: candidato Sherpa, resumen de identidad del motor, conjunto explícito auditado, hablantes con texto e identidades sin texto.
- `identity_wall_seconds` es el total de identidad; conservar `final_stage_wall_seconds`, `light_identity_wall_seconds` y `total_wall_seconds`.

### Presets globales y migración

Un preset V5.2.1 es una configuración **completa**, no una etiqueta parcial:

- Rápido: small / ASR Rápido / Hablantes Auto / Rápida 0.25.
- Equilibrado: small / ASR Equilibrado / Hablantes Auto / Equilibrada 0.20.
- Preciso: medium / ASR Preciso / Hablantes Auto / Equilibrada 0.20.
- Personalizado: controles libres, incluida Precisa 0.10.

No introducir presets que sobreescriban opciones existentes. La UI V5.2.1 solo reconoce el preset vigente cuando coinciden también activación de diarización y modo de hablantes. Las firmas históricas V5.1 se mantienen únicamente para compatibilidad de inferencia legacy y no autorizan una migración silenciosa del estado actual.

### Métricas y reporting

- `processing_seconds = ASR + diarización + exportación + overhead`.
- `report_generation_seconds` se mide aparte para evitar regenerar infinitamente un informe para incluir el tiempo de su propia escritura.
- `end_to_end_seconds = carga de modelo + processing + generación de informes`.
- `performance` se recalcula desde los tiempos definitivos. No copiar un estado `within_realtime` previo a exportación.
- El DOCX V5.2.1 se construye directamente y debe efectuar un único `Document.save()` por salida final.
- El JSON final es la fuente autoritativa para `report_generation_seconds` y `end_to_end_seconds`, porque el DOCX no puede conocer el tiempo de su propia escritura antes de guardarse.

## 4. Modelos de diarización

Los hashes fijados en `vtt_diarization.py` corresponden a assets oficiales k2-fsa auditados por VtT. No reemplazarlos por valores calculados desde una descarga nueva sin revisión expresa. Un cambio upstream requiere revisar tamaño/hash, smoke acústico y documentación.

## 5. Android

- Trabajo: `TranscribeViewModel`.
- `Transcriber` sincroniza carga/transcripción/liberación.
- JNI usa handles opacos/shared_ptr y aborto atómico.
- >5 min: procesamiento por bloques 90 s + 2 s de solapamiento.
- Modelos GGML deben coincidir con SHA-256 esperado antes de la primera promoción.

No eliminar solapamiento/deduplicación ni volver al PCM completo sin medir timestamps, memoria y calidad. Android sigue sin diarización.

## 6. Verificación obligatoria

Si se toca `desktop/*.py`:

```text
python -m py_compile <módulos afectados>
python -m pytest tests -q
```

Cierre oficial: `Desktop checks` en Windows/macOS/Ubuntu.

Si se toca reporting, deben existir regresiones de campos/etiquetas y número de escrituras afectadas.

Si se toca empaquetado/imports del entrypoint: `Desktop executables` en los tres SO.

Si se toca `android/`: `Android APK` verde. Hardware real sigue siendo manual.

Si se toca diarización/identidad/model pins: pruebas de lógica + smoke con ground truth conocido cuando sea posible.

La suite V5.2.1 debe conservar regresiones de:

- cancelación compartida;
- checkpoint ASR;
- conteos acústicos vs texto;
- performance final/end-to-end;
- DOCX de un guardado;
- presets completos;
- presupuesto de retry.

## 7. Documentación

Actualizar README/plan/auditoría cuando cambien mínimos, entrypoint, schema JSON, presets, dependencias, seguridad, métricas o limitaciones.

`AUDITORIA.md` concentra IDs concretos de campañas CI/build; los README priorizan comportamiento vigente.

## 8. Qué no hacer

- No reescribir en Electron/Qt/web sin decisión de producto.
- No usar `sounddevice.WasapiSettings(loopback=True)`; Windows loopback usa `soundcard`.
- No afirmar que Android tiene diarización.
- No presentar confianza acústica como biometría.
- No volver a usar Precisa 0.10 como preset global por intuición.
- No añadir otra caché Whisper sin demostrar que la reutilización existente es insuficiente.
- No repetir indefinidamente una estrategia fallida: tras dos fallos de la misma causa, cambiar de enfoque.