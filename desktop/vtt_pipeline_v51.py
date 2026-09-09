#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pipeline V5.1: consistencia acústica de identidad y reportes de confianza."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import transcriptor_whisper as base
import vtt_core as core
import vtt_diarization_service_v51 as dservice51
import vtt_pipeline_v5 as v5
import vtt_reporting_v51 as reporting51
import vtt_validation_v51 as validation51


class PipelineV51Mixin(v5.PipelineV5Mixin):
    def _diar_service(self):
        svc = getattr(self, "_v51_diar_service", None)
        if svc is None:
            svc = dservice51.PersistentDiarizationService(base.CARPETA_DATOS / "modelos_hablantes")
            self._v51_diar_service = svc
        return svc

    def _diarizar_pipeline(self, archivo: str, segs, dur: float, opts, log):
        asignados, speakers, meta = super()._diarizar_pipeline(archivo, segs, dur, opts, log)
        meta = dict(meta or {})
        raw_to_display = {
            int(s.get("raw_numeric_id")): str(s.get("display_name"))
            for s in speakers if s.get("raw_numeric_id") is not None
        }
        consistency = dict(meta.get("identity_consistency") or {})
        for item in consistency.get("speakers", []) or []:
            try:
                item["display_name"] = raw_to_display.get(int(item.get("speaker")))
            except (TypeError, ValueError):
                item["display_name"] = None
        meta["identity_consistency"] = consistency
        meta["speaker_count_validation"] = validation51.aplicar_consistencia_identidad(
            meta.get("speaker_count_validation") or {}, consistency
        )
        if meta["speaker_count_validation"].get("status") in {
            "estimacion_sospechosa_identidad", "estimacion_con_reservas_identidad"
        }:
            log("Conteo/identidades: resultado con reservas; revisar voces antes de usarlo como definitivo.")
        return asignados, speakers, meta

    def _metricas_base(
        self, dur: float, perfil: Mapping[str, Any], perfil_nombre: str,
        device: str, compute: str, opts, model_load_seconds: float,
        asr_seconds: float, diar_seconds: float, speakers,
        diar_meta: Mapping[str, Any], overhead_seconds: float = 0.0,
    ):
        m = super()._metricas_base(
            dur, perfil, perfil_nombre, device, compute, opts,
            model_load_seconds, asr_seconds, diar_seconds, speakers,
            diar_meta, overhead_seconds,
        )
        iv = diar_meta.get("identity_verification") or {}
        m.update({
            "speaker_count_validation": diar_meta.get("speaker_count_validation") or {},
            "identity_verification": iv,
            "identity_refinement": diar_meta.get("identity_refinement") or {},
            "identity_local_scan": diar_meta.get("identity_local_scan") or {},
            "identity_consistency": diar_meta.get("identity_consistency") or {},
            "identity_wall_seconds": diar_meta.get("identity_wall_seconds", 0.0),
            "identity_embedding_compute_seconds": iv.get("embedding_compute_seconds", 0.0),
            "identity_embedding_calls": iv.get("embedding_calls", 0),
            "identity_embedding_cache_hits": iv.get("embedding_cache_hits", 0),
            "speaker_detected_before_identity": diar_meta.get("detected_speakers_before_identity"),
        })
        return m

    def _reescribir_reportes(
        self, paths, archivo, modelo, idioma, texto, segs, bloques,
        speakers, metricas, perfil, glosario,
    ):
        if paths.get("json"):
            doc = reporting51.documento_json_detallado(
                archivo, modelo, idioma, texto, segs, bloques,
                speakers, metricas, perfil, glosario,
            )
            Path(paths["json"]).write_text(core.json_texto(doc), encoding="utf-8")
        if paths.get("docx"):
            reporting51.escribir_docx_detallado(
                Path(paths["docx"]), archivo, modelo, idioma,
                bloques, metricas, perfil,
            )
