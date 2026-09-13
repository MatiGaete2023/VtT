# AGENTS.md — VtT Ultra Windows

Contrato de esta rama: `windows-ultra-fast`.

## Objetivo

Esta rama prioriza **Windows 10/11 + CPU + velocidad**. No debe retrasarse una mejora útil para Windows por compatibilidad específica con macOS/Linux. La rama estable V5.2.1 conserva la variante multiplataforma completa.

## Invariantes

1. Audio local/offline y sin telemetría.
2. Windows normal sin privilegios de administrador.
3. No perder ASR ya completado: conservar checkpoint recuperable ante cancelación/fallo posterior.
4. Auto de hablantes es estimación, no ground truth.
5. No sobrescribir salidas silenciosamente.
6. No añadir servicios cloud para acelerar el audio.
7. Mantener cancelación mediante `vtt_diarization_errors.DiarizacionCancelada`.
8. Mantener modelos/hashes auditados heredados.
9. Todo cambio funcional debe tener regresión y CI Windows.
10. PyInstaller requerido si cambia entrypoint/imports.

## Estrategia Ultra actual

- Whisper `tiny`.
- ASR `Rapido`: batch 8, beam 1.
- Hablantes Auto.
- Perfil de diarización `Ultrarrápida`, shift 0.35.
- Threshold Auto 0.82.
- **Una sola pasada Sherpa**.
- Sin refinamiento/consistencia de identidad V5.2.
- Sin timestamps por palabra forzados por diarización.
- Alineación `segment_overlap` mediante timestamps del segmento ASR.
- Worker Sherpa persistente.
- Reducción a regiones de voz cuando es segura.

Estos tradeoffs son deliberados. No reintroducir segunda pasada, identidad V5.2 o word timestamps obligatorios sin benchmark Windows que demuestre que el costo merece la pena.

## Archivos propios de la variante

- `desktop/vtt_ultra_config.py`
- `desktop/vtt_pipeline_ultra.py`
- `desktop/vtt_ui_ultra.py`
- `desktop/tests/test_vtt_ultra.py`
- `ULTRA_WINDOWS.md`

`desktop/vtt_main.py` compone estas capas en esta rama.

Los módulos V4/V5/V5.1/V5.2 permanecen como base heredada. No eliminarlos sin revisar imports/MRO.

## Verificación

Para cambios Python:

```text
python -m py_compile <módulos afectados>
python -m pytest tests -q
```

Cierre oficial de esta rama: workflow **Windows Ultra checks**.

Si cambia entrypoint/imports: construir **VtT-Ultra-Windows.exe** mediante PyInstaller en `windows-latest`.

No se exige CI macOS/Linux para esta rama.

## Benchmark real

La validación principal debe hacerse en el PC Windows institucional y con el mismo audio de referencia utilizado en V5.2.1.

Registrar:

- `model_load_seconds`;
- `asr_seconds`;
- `diarization_seconds`;
- `sherpa_process_wall_seconds`;
- tiempos internos Sherpa si existen;
- clusters acústicos y hablantes con texto;
- `processing_seconds`;
- `end_to_end_seconds`;
- errores evidentes de asignación de Persona N.

No afirmar mejora acústica ni velocidad final sin esa prueba.
