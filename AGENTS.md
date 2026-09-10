# AGENTS.md — Reglas del repositorio VtT

Contrato para cualquier persona o agente que modifique este repositorio.

## 1. Producto y plataformas

VtT tiene dos aplicaciones relacionadas pero no equivalentes:

- `desktop/`: Python/Tkinter, faster-whisper y diarización sherpa-onnx V5.2.
- `android/`: Kotlin + whisper.cpp/JNI. Android no incorpora diarización del escritorio.

## 2. Reglas inquebrantables

1. **Offline-first y privado.** El audio del usuario no se envía a servicios de transcripción.
2. **Sin telemetría.** No añadir analytics/tracking.
3. **Instalación simple.** Escritorio Python 3.9+; Android APK.
4. **Sin privilegios de administrador en Windows normal.** Documentar requisitos de sistema de Linux/macOS cuando existan.
5. **Nunca perder trabajo.** No sobrescribir silenciosamente grabaciones/exportaciones.
6. **No confundir estimación con certeza.** Auto y confianza acústica no son ground truth.
7. **Idioma del producto:** UI, mensajes y documentación en español.
8. **Compatibilidad:** escritorio Python ≥3.9; Android minSdk 24 y ARM64 salvo decisión expresa.
9. **No versionar** venv, modelos descargados, grabaciones, transcripciones, builds/APK o temporales.
10. **Verificar APIs externas** contra la versión realmente utilizada.
11. **No inventar hashes.** Distinguir un digest publicado por upstream de un pin auditado/reproducido por VtT.
12. **Supply chain:** workflows de CI/build deben preferir acciones fijadas por SHA y revisiones explícitas.
13. **Cambios con verificación.** Definir y ejecutar la comprobación antes de cerrar.
14. **Infraestructura temporal:** eliminar workflows/triggers temporales después de recopilar evidencia.
15. **Versionado visible coherente.** Un reporte generado por V5.2 no debe mostrar rótulos V5.1 salvo que se esté describiendo explícitamente una etapa histórica o compatibilidad.

## 3. Arquitectura de escritorio

Entry point final: `desktop/vtt_main.py`.

Capas actuales:

- `vtt_core.py`: estructuras, bloques y exportación base.
- `vtt_alignment.py`: alineación palabra↔hablante.
- `vtt_diarization_v5.py`: motor persistente e instrumentación base.
- `vtt_identity_v52.py`: identidad rival-aware y sonda de turnos largos.
- `vtt_diarization_v52.py`: precheck Auto, selección identity-aware y reutilización acústica.
- `vtt_diarization_v52_metrics.py`: contabilidad completa de evaluaciones ligeras + etapa final de identidad.
- `vtt_diarization_service_v52.py`: worker persistente efectivo usado por el pipeline final.
- `vtt_validation_v52.py`: conteos/validación por etapa.
- `vtt_reporting_v52.py`: JSON schema v7 y DOCX diagnóstico.
- `vtt_performance.py`: modos globales y presupuesto de rendimiento.
- `vtt_pipeline_v52.py`: pipeline final.
- `vtt_ui_v52.py`: UI de modos globales y migración conservadora.

Los módulos `v4`, `v5` y `v51` permanecen porque V5.2 hereda de esas capas. No eliminarlos ni tratarlos como código muerto solo por el nombre de versión sin comprobar la cadena real de imports/MRO.

No volver a concentrar lógica nueva en `transcriptor_whisper.py` si puede vivir en una capa específica.

### Hilos y Tk

Los workers no modifican widgets directamente. Usar colas y `root.after`/mecanismos existentes. Mantener diarización fuera del hilo UI.

### Diarización/identidad

- Equilibrada es la recomendación general.
- Precisa tiene alto costo CPU.
- Una intervención breve no se fusiona solo por duración.
- Turnos largos no forman prototipos si pueden contener varias voces.
- El precheck V5.2 tiene presupuesto acotado; no debe transformarse en otra diarización completa.
- En modo manual N, no crear identidades adicionales automáticamente sin decisión explícita.
- Mantener separados clusters sherpa, clusters tras identidad y hablantes con texto.
- `identity_wall_seconds` es el total de identidad; el desglose V5.2 debe conservar `final_stage_wall_seconds`, `light_identity_wall_seconds` y `total_wall_seconds`.

### Migración de configuración

No introducir presets que sobreescriban opciones existentes. Una configuración previa solo puede reconocerse como preset si coincide de forma inequívoca; de lo contrario debe conservarse como Personalizado.

## 4. Modelos de diarización

Los hashes fijados en `vtt_diarization.py` corresponden a assets oficiales k2-fsa auditados por VtT. No reemplazarlos por valores calculados desde una descarga nueva sin una revisión expresa. Un cambio upstream requiere revisar tamaño/hash, smoke acústico y documentación.

## 5. Android

- Trabajo: `TranscribeViewModel`.
- `Transcriber` sincroniza carga/transcripción/liberación.
- JNI usa handles opacos/shared_ptr y aborto atómico.
- >5 min: procesamiento por bloques 90 s + 2 s de solapamiento.
- Modelos GGML deben coincidir con el SHA-256 esperado antes de la primera promoción.

No eliminar el solapamiento/deduplicación ni volver al PCM completo sin medir timestamps, memoria y calidad. Android sigue sin diarización.

## 6. Verificación obligatoria

Si se toca `desktop/*.py`:

```text
python -m py_compile <módulos afectados>
python -m pytest tests -q
```

Cierre oficial: `Desktop checks` en Windows/macOS/Ubuntu.

Si se toca reporting, además de verificar sintaxis deben existir regresiones de las etiquetas/campos visibles afectados. No aceptar que una capa heredada vuelva a introducir nombres de versión obsoletos en Word/JSON.

Si se toca empaquetado/imports del entrypoint: `Desktop executables` en los tres SO.

Si se toca `android/`: `Android APK` verde. Hardware real sigue siendo manual.

Si se toca diarización/identidad/model pins: pruebas de lógica + smoke con ground truth conocido cuando sea posible.

## 7. Documentación

Actualizar los README/plan/auditoría cuando cambien mínimos, entrypoint, schema JSON, perfiles, dependencias, seguridad de modelos, métricas o limitaciones.

`AUDITORIA.md` concentra IDs concretos de campañas CI/build; los README deben priorizar el comportamiento vigente para reducir referencias que envejecen con cada ejecución.

## 8. Qué no hacer

- No reescribir en Electron/Qt/web sin decisión de producto.
- No usar `sounddevice.WasapiSettings(loopback=True)`; Windows loopback usa `soundcard`.
- No afirmar que Android tiene diarización.
- No presentar confianza acústica como biometría.
- No repetir indefinidamente una estrategia fallida: tras dos fallos de la misma causa, cambiar de enfoque.
