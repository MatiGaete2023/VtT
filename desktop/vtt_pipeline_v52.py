#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pipeline V5.2: rendimiento, conteos explícitos y Auto identity-aware."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import transcriptor_whisper as base
import vtt_core as core
import vtt_diarization_service_v52 as dservice52
import vtt_performance as perf
import vtt_pipeline_v51 as v51
import vtt_reporting_v52 as reporting52
import vtt_validation_v52 as validation52


class PipelineV52Mixin(v51.PipelineV51Mixin):
    def _diar_service(self):
        svc = getattr(self, "_v52_diar_service", None)
        if svc is None:
            svc = dservice52.PersistentDiarizationService(
                base.CARPETA_DATOS / "modelos_hablantes"
            )
            self._v52_diar_service = svc
        return svc

    def _diarizar_pipeline(self, archivo: str, segs, dur: float, opts, log):
        asignados, speakers, meta = super()._diarizar_pipeline(
            archivo, segs, dur, opts, log
        )
        meta = dict(meta or {})
        consistency = dict(meta.get("identity_consistency") or {})

        raw = int(
            meta.get("raw_sherpa_selected_speakers")
            or meta.get("detected_speakers_before_identity")
            or meta.get("detected_speakers")
            or 0
        )
        identity_n = int(meta.get("detected_speakers", raw) or raw)
        text_n = len(speakers or [])
        assigned_raw = {
            int(s.get("raw_numeric_id")) for s in (speakers or [])
            if s.get("raw_numeric_id") is not None
        }
        all_identity_raw = {
            int(s.get("speaker")) for s in (consistency.get("speakers") or [])
            if s.get("speaker") is not None
        }
        unassigned = sorted(all_identity_raw - assigned_raw)
        counts = {
            "raw_acoustic_clusters": raw,
            "identity_clusters_after_refinement": identity_n,
            "text_assigned_speakers": text_n,
            "unassigned_acoustic_clusters": len(unassigned),
            "unassigned_raw_ids": unassigned,
        }
        meta["speaker_counts"] = counts

        modo = str(opts.get("num_speakers", "Auto"))
        requested = None if modo == "Auto" else int(modo)
        meta["speaker_count_validation"] = validation52.evaluar(
            meta, acoustic_clusters=raw, identity_clusters=identity_n,
            text_speakers=text_n, unassigned_raw_ids=unassigned,
            manual_requested=requested,
        )
        if raw != text_n:
            log(
                "Conteo V5.2: "
                f"{raw} cluster(s) acústico(s) seleccionado(s) · "
                f"{identity_n} tras identidad · {text_n} con texto."
            )
        if meta["speaker_count_validation"].get("ambiguous"):
            log("Auto V5.2: resultado ambiguo; se conserva trazabilidad completa en JSON/Word.")
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
        counts = dict(diar_meta.get("speaker_counts") or {})
        if counts:
            m["speaker_detected"] = int(
                counts.get("identity_clusters_after_refinement", m.get("speaker_detected", 0)) or 0
            )
            m["speaker_text_assigned"] = int(counts.get("text_assigned_speakers", len(speakers or [])) or 0)
        m.update({
            "speaker_counts": counts,
            "speaker_count_validation": diar_meta.get("speaker_count_validation") or {},
            "auto_precheck": diar_meta.get("auto_precheck") or {},
            "auto_retry_requested": bool(diar_meta.get("retry_requested", False)),
            "auto_retry_avoided": bool(diar_meta.get("retry_avoided", False)),
            "identity_aware_selection": diar_meta.get("identity_aware_selection") or {},
            "global_profile": getattr(self, "_global_profile_run", None),
        })
        m["performance"] = perf.performance_status(m)
        return m

    def _reescribir_reportes(
        self, paths, archivo, modelo, idioma, texto, segs, bloques,
        speakers, metricas, perfil, glosario,
    ):
        if paths.get("json"):
            doc = reporting52.documento_json_detallado(
                archivo, modelo, idioma, texto, segs, bloques,
                speakers, metricas, perfil, glosario,
            )
            Path(paths["json"]).write_text(core.json_texto(doc), encoding="utf-8")
        if paths.get("docx"):
            reporting52.escribir_docx_detallado(
                Path(paths["docx"]), archivo, modelo, idioma,
                bloques, metricas, perfil,
            )
