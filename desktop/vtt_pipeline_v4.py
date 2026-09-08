#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pipeline V4: conecta perfiles y Auto estructural de diarización."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Mapping

import transcriptor_whisper as base
import vtt_core as core
import vtt_diarization_process_v4 as dproc4
import vtt_pipeline as v3
import vtt_reporting_v4 as reporting4
import vtt_tuning as tuning


class PipelineV4Mixin(v3.PipelineV3Mixin):
    def _diarizar_pipeline(self, archivo: str, segs, dur: float, opts, log):
        modo = str(opts.get("num_speakers", "Auto"))
        ns = -1 if modo == "Auto" else int(modo)
        perfil_diar = str(
            getattr(self, "_diar_profile_run", "Equilibrada") or "Equilibrada"
        )

        regiones, reduccion_pre = tuning.regiones_voz_desde_segmentos(segs, dur)
        if reduccion_pre.get("enabled"):
            log(
                "Regiones de voz candidatas: "
                f"{float(reduccion_pre.get('coverage', 0.0))*100:.0f}% del audio; "
                f"ahorro potencial ~{base.ts_simple(reduccion_pre.get('saved_seconds', 0.0))}."
            )
        else:
            log(
                "Regiones de voz: se conserva audio completo "
                f"({reduccion_pre.get('reason', 'sin ahorro seguro')})."
            )

        inicio = time.monotonic()
        nombre = Path(archivo).name
        self._cola_diar_ui.put((0.0, None, nombre))

        def avance(pct: float):
            self._emitir_progreso_diarizacion(pct, inicio, nombre)

        try:
            turnos, meta = dproc4.diarizar_responsivo(
                archivo,
                base.CARPETA_DATOS / "modelos_hablantes",
                num_speakers=ns,
                threshold=0.5,
                log=log,
                progreso=avance,
                cancelado=self.cancelar.is_set,
                speech_regions=regiones if reduccion_pre.get("enabled") else None,
                adaptive=(ns < 0),
                diar_profile=perfil_diar,
                return_meta=True,
            )
        except dproc4.DiarizacionCancelada:
            raise base.Cancelado()

        asignados, _ = core.asignar_hablantes(segs, turnos)
        asignados, speakers = tuning.renumerar_hablantes_en_uso(asignados)
        meta = dict(meta or {})
        meta["wall_seconds"] = time.monotonic() - inicio
        meta["detected_speakers"] = len(speakers)
        return asignados, speakers, meta

    def _metricas_base(
        self,
        dur: float,
        perfil: Mapping[str, Any],
        perfil_nombre: str,
        device: str,
        compute: str,
        opts,
        model_load_seconds: float,
        asr_seconds: float,
        diar_seconds: float,
        speakers,
        diar_meta: Mapping[str, Any],
        overhead_seconds: float = 0.0,
    ):
        m = super()._metricas_base(
            dur,
            perfil,
            perfil_nombre,
            device,
            compute,
            opts,
            model_load_seconds,
            asr_seconds,
            diar_seconds,
            speakers,
            diar_meta,
            overhead_seconds,
        )
        m.update({
            "diarization_profile": diar_meta.get("diarization_profile"),
            "window_shift_ratio": diar_meta.get("window_shift_ratio"),
            "auto_passes": diar_meta.get("passes", 1),
            "auto_selection_reason": diar_meta.get("selection_reason"),
            "auto_retry_reason": diar_meta.get("retry_reason"),
            "auto_stability_delta_speakers": diar_meta.get(
                "stability_delta_speakers"
            ),
            "auto_selected_analysis": diar_meta.get("selected_analysis"),
            "auto_candidates": diar_meta.get("candidates") or [],
        })
        return m

    def _reescribir_reportes(
        self,
        paths,
        archivo,
        modelo,
        idioma,
        texto,
        segs,
        bloques,
        speakers,
        metricas,
        perfil,
        glosario,
    ):
        if paths.get("json"):
            doc = reporting4.documento_json_detallado(
                archivo,
                modelo,
                idioma,
                texto,
                segs,
                bloques,
                speakers,
                metricas,
                perfil,
                glosario,
            )
            Path(paths["json"]).write_text(
                core.json_texto(doc), encoding="utf-8"
            )
        if paths.get("docx"):
            reporting4.escribir_docx_detallado(
                Path(paths["docx"]),
                archivo,
                modelo,
                idioma,
                bloques,
                metricas,
                perfil,
            )
