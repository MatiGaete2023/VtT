#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pipeline especializado de VtT Ultra Windows.

Diferencias deliberadas frente a V5.2.1 estable:
- no fuerza timestamps por palabra por activar diarización;
- una sola pasada sherpa, sin retry Auto;
- no ejecuta refinamiento/consistencia de identidad V5.2;
- asigna hablante al segmento ASR por máximo solapamiento temporal;
- conserva timestamps de segmento, speaker labels y métricas de la pasada.

El objetivo es reducir drásticamente el tiempo total en CPU Windows. El costo es
menor resolución en cambios de voz dentro de un mismo segmento y menor robustez
para reconciliar identidades acústicas dudosas.
"""
from __future__ import annotations

import queue
import time
from pathlib import Path
from typing import Any, Dict, Mapping

import transcriptor_whisper as base
import vtt_core as core
import vtt_diarization_service as dservice
from vtt_diarization_errors import DiarizacionCancelada
import vtt_pipeline as v3
import vtt_pipeline_v52 as v52
import vtt_tuning as tuning
import vtt_validation_v52 as validation52
from vtt_ultra_config import (
    ULTRA_AUTO_THRESHOLD,
    ULTRA_DIAR_PROFILE,
    ultra_threshold_for_speaker_mode,
    ultra_tradeoffs,
    ultra_word_timestamps,
)


def ultra_speaker_counts(turns, speakers) -> Dict[str, Any]:
    raw_ids = {int(t.get("speaker", 0)) for t in (turns or [])}
    assigned_ids = {
        int(s.get("raw_numeric_id")) for s in (speakers or [])
        if s.get("raw_numeric_id") is not None
    }
    unassigned = sorted(raw_ids - assigned_ids)
    assigned_unknown = sorted(assigned_ids - raw_ids)
    return {
        "raw_acoustic_clusters": len(raw_ids),
        "engine_identity_clusters": len(raw_ids),
        "identity_consistency_clusters": 0,
        "identity_clusters_after_refinement": len(raw_ids),
        "text_assigned_speakers": len(speakers or []),
        "unassigned_acoustic_clusters": len(unassigned),
        "unassigned_raw_ids": unassigned,
        "text_ids_missing_from_identity_audit": assigned_unknown,
        "identity_count_mismatch": False,
    }


class PipelineUltraMixin(v52.PipelineV52Mixin):
    """Ruta de máxima velocidad para CPU Windows."""

    def _worker_vtt(self, archivos, modelo, idioma, salida, formatos, vad, words, opts):
        # V5 fuerza word_timestamps al activar diarización. Ultra no lo hace:
        # conservar timestamps de segmento es suficiente para la asignación
        # rápida por solapamiento. Si el usuario pide palabras, se respetan.
        self._v5_user_words_run = bool(words)
        self._v5_forced_words_run = False
        effective_words = ultra_word_timestamps(bool(words))
        if opts.get("diarizar") and not effective_words:
            self.cola.put((
                "log",
                "Ultra Windows: timestamps por palabra NO forzados; "
                "se usan tiempos de segmento para ahorrar ASR/alineación.",
            ))
        return v3.PipelineV3Mixin._worker_vtt(
            self, archivos, modelo, idioma, salida, formatos, vad,
            effective_words, opts,
        )

    def _diar_service(self):
        svc = getattr(self, "_ultra_diar_service", None)
        if svc is None:
            svc = dservice.PersistentDiarizationService(
                base.CARPETA_DATOS / "modelos_hablantes"
            )
            self._ultra_diar_service = svc
        return svc

    def _prepare_diarization_opts(self, dur: float, asr_seconds: float, opts):
        out = dict(opts)
        out["_ultra_fast"] = True
        # Ultra nunca paga una segunda pasada, por lo que no necesita reservar
        # presupuesto para retry. Se conserva este dato como diagnóstico.
        out["_diar_time_budget_seconds"] = max(
            0.0, float(dur or 0.0) * 0.60 - float(asr_seconds or 0.0)
        )
        return out

    def _diarizar_pipeline(self, archivo: str, segs, dur: float, opts, log):
        mode = str(opts.get("num_speakers", "Auto"))
        ns = -1 if mode == "Auto" else int(mode)
        profile = str(
            getattr(self, "_diar_profile_run", ULTRA_DIAR_PROFILE)
            or ULTRA_DIAR_PROFILE
        )
        threshold = ultra_threshold_for_speaker_mode(mode)

        regions, reduction = tuning.regiones_voz_desde_segmentos(segs, dur)
        if reduction.get("enabled"):
            log(
                "Ultra: diarización limitada a regiones de voz "
                f"({float(reduction.get('coverage', 0.0))*100:.0f}% del audio)."
            )
        else:
            log("Ultra: no fue seguro reducir el audio; se procesa completo.")

        start = time.monotonic()
        name = Path(archivo).name
        self._cola_diar_ui.put((0.0, None, name))

        def progress(pct: float):
            self._emitir_progreso_diarizacion(pct, start, name)

        try:
            turns, meta = self._diar_service().diarize(
                archivo,
                num_speakers=ns,
                threshold=threshold,
                log=log,
                progreso=progress,
                cancelado=self.cancelar.is_set,
                speech_regions=regions if reduction.get("enabled") else None,
                # Clave del modo Ultra: sherpa se ejecuta exactamente una vez.
                adaptive=False,
                diar_profile=profile,
            )
        except DiarizacionCancelada:
            raise base.Cancelado()

        assigned, _ = core.asignar_hablantes(segs, turns)
        assigned, speakers = tuning.renumerar_hablantes_en_uso(assigned)

        meta = dict(meta or {})
        raw_count = len({int(t.get("speaker", 0)) for t in turns})
        counts = ultra_speaker_counts(turns, speakers)
        meta.update({
            "wall_seconds": max(
                float(meta.get("wall_seconds", 0.0) or 0.0),
                time.monotonic() - start,
            ),
            "ultra_fast_mode": True,
            "ultra_strategy": "one_pass_segment_alignment",
            "ultra_tradeoffs": ultra_tradeoffs(),
            "raw_sherpa_selected_speakers": raw_count,
            "detected_speakers": raw_count,
            "detected_speakers_engine": raw_count,
            "text_assigned_speakers": len(speakers),
            "assigned_raw_speaker_ids": sorted({
                int(s.get("raw_numeric_id")) for s in speakers
                if s.get("raw_numeric_id") is not None
            }),
            "passes": 1,
            "retry": False,
            "retry_requested": False,
            "retry_avoided": True,
            "retry_skipped_budget": False,
            "selection_reason": "ultra_una_pasada",
            "selected_threshold": None if ns >= 0 else threshold,
            "identity_verification": {
                "enabled": False,
                "reason": "omitida_por_modo_ultra_rapido",
            },
            "identity_consistency": {},
            "identity_refinement": {},
            "identity_local_scan": {},
            "identity_wall_seconds": 0.0,
            "alignment": {
                "mode": "segment_overlap",
                "input_segments": len(segs or []),
                "output_segments": len(assigned or []),
                "speaker_switches_inside_segments": 0,
                "word_level": False,
            },
            "word_timestamps_forced_for_diarization": False,
            "speaker_counts": counts,
        })
        requested = None if mode == "Auto" else int(mode)
        meta["speaker_count_validation"] = validation52.evaluar(
            meta,
            acoustic_clusters=raw_count,
            identity_clusters=raw_count,
            text_speakers=len(speakers),
            unassigned_raw_ids=counts["unassigned_raw_ids"],
            manual_requested=requested,
        )
        if mode == "Auto":
            # No se hizo validación de identidad: la cifra es deliberadamente
            # una estimación rápida y debe reportarse como tal.
            meta["speaker_count_validation"]["ambiguous"] = True
            meta["speaker_count_validation"]["ultra_fast_limited"] = True
            meta["speaker_count_validation"]["status"] = "estimacion_ultra_una_pasada"

        internal = meta.get("sherpa_internal") or {}
        log(
            "Ultra: una sola pasada sherpa · "
            f"threshold {threshold:.2f} · {raw_count} cluster(s) acústico(s) · "
            f"{len(speakers)} con texto."
        )
        if meta.get("sherpa_internal_timing_available"):
            log(
                "Sherpa Ultra: "
                f"segmentación {float(internal.get('segmentation_seconds', 0.0)):.2f}s · "
                f"embeddings {float(internal.get('embedding_seconds', 0.0)):.2f}s · "
                f"clustering {float(internal.get('clustering_seconds', 0.0)):.2f}s."
            )
        return assigned, speakers, meta

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
        m.update({
            "ultra_fast_mode": True,
            "ultra_one_pass": True,
            "ultra_auto_threshold": ULTRA_AUTO_THRESHOLD,
            "ultra_alignment": "segment_overlap",
            "ultra_identity_verification": False,
            "ultra_tradeoffs": ultra_tradeoffs(),
        })
        return self._recalcular_metricas_finales(m)
