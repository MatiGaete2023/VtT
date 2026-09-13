#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pipeline especializado de VtT Ultra Windows.

La rama ofrece dos variantes:
- Ultrarrápido: tiny, una pasada sherpa, alineación por segmento;
- Ultra Calidad 90s: base, una pasada sherpa, timestamps por palabra,
  alineación fina y verificación de identidad ligera/acotada.

Ninguna variante ejecuta una segunda pasada sherpa. El re-ASR selectivo queda
explícitamente desactivado hasta medir el presupuesto real en el PC objetivo.
"""
from __future__ import annotations

import queue
import time
from pathlib import Path
from typing import Any, Dict, Mapping

import transcriptor_whisper as base
import vtt_alignment as alignment
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
    ULTRA_PROFILE_NAME,
    ULTRA_QUALITY_PROFILE_NAME,
    ULTRA_QUALITY_TARGET_PROCESSING_RATIO,
    ULTRA_TARGET_PROCESSING_RATIO,
    is_ultra_quality,
    ultra_threshold_for_speaker_mode,
    ultra_tradeoffs,
    ultra_word_timestamps,
)


def ultra_speaker_counts(turns, speakers, raw_sherpa_ids=None) -> Dict[str, Any]:
    identity_ids = {int(t.get("speaker", 0)) for t in (turns or [])}
    raw_ids = {
        int(x) for x in (
            raw_sherpa_ids if raw_sherpa_ids is not None else identity_ids
        )
    }
    assigned_ids = {
        int(s.get("raw_numeric_id")) for s in (speakers or [])
        if s.get("raw_numeric_id") is not None
    }
    unassigned = sorted(identity_ids - assigned_ids)
    assigned_unknown = sorted(assigned_ids - identity_ids)
    return {
        "raw_acoustic_clusters": len(raw_ids),
        "raw_sherpa_ids": sorted(raw_ids),
        "engine_identity_clusters": len(identity_ids),
        "identity_consistency_clusters": len(identity_ids),
        "identity_clusters_after_refinement": len(identity_ids),
        "text_assigned_speakers": len(speakers or []),
        "unassigned_acoustic_clusters": len(unassigned),
        "unassigned_raw_ids": unassigned,
        "text_ids_missing_from_identity_audit": assigned_unknown,
        "identity_count_mismatch": bool(assigned_unknown),
    }


class PipelineUltraMixin(v52.PipelineV52Mixin):
    """Rutas Ultra de máxima velocidad y calidad acotada para CPU Windows."""

    def _ultra_profile_run(self) -> str:
        return str(getattr(self, "_global_profile_run", ULTRA_PROFILE_NAME) or ULTRA_PROFILE_NAME)

    def _worker_vtt(self, archivos, modelo, idioma, salida, formatos, vad, words, opts):
        profile_name = self._ultra_profile_run()
        quality = is_ultra_quality(profile_name)
        self._v5_user_words_run = bool(words)
        effective_words = ultra_word_timestamps(bool(words), profile_name)
        self._v5_forced_words_run = bool(
            quality and opts.get("diarizar") and not bool(words)
        )
        if self._v5_forced_words_run:
            self.cola.put((
                "log",
                "Ultra Calidad 90s: timestamps por palabra activados internamente "
                "para recuperar cambios de voz dentro de segmentos.",
            ))
        elif opts.get("diarizar") and not effective_words:
            self.cola.put((
                "log",
                "Ultra Máxima: timestamps por palabra NO forzados; "
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
        profile_name = self._ultra_profile_run()
        quality = is_ultra_quality(profile_name)
        ratio = (
            ULTRA_QUALITY_TARGET_PROCESSING_RATIO
            if quality else ULTRA_TARGET_PROCESSING_RATIO
        )
        out["_ultra_fast"] = True
        out["_ultra_quality"] = quality
        out["_diar_time_budget_seconds"] = max(
            0.0, float(dur or 0.0) * ratio - float(asr_seconds or 0.0)
        )
        return out

    def _diarizar_pipeline(self, archivo: str, segs, dur: float, opts, log):
        profile_name = self._ultra_profile_run()
        quality = is_ultra_quality(profile_name)
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
                # Invariante Ultra: sherpa se ejecuta exactamente una vez.
                adaptive=False,
                diar_profile=profile,
                identity_lite=quality,
                time_budget_seconds=opts.get("_diar_time_budget_seconds"),
            )
        except DiarizacionCancelada:
            raise base.Cancelado()

        if quality:
            assigned, align_meta = alignment.alinear_y_dividir(segs, turns)
        else:
            assigned, _ = core.asignar_hablantes(segs, turns)
            align_meta = {
                "mode": "segment_overlap",
                "input_segments": len(segs or []),
                "output_segments": len(assigned or []),
                "speaker_switches_inside_segments": 0,
                "word_level": False,
            }
        assigned, speakers = tuning.renumerar_hablantes_en_uso(assigned)

        # Los timestamps por palabra pueden ser internos. Solo se exportan si el
        # usuario los pidió explícitamente.
        if not bool(getattr(self, "_v5_user_words_run", False)):
            for seg in assigned:
                seg["words"] = []

        meta = dict(meta or {})
        raw_ids = list(meta.get("raw_sherpa_ids") or [])
        raw_count = int(
            meta.get("raw_sherpa_selected_speakers")
            or len(set(raw_ids))
            or len({int(t.get("speaker", 0)) for t in turns})
        )
        identity_count = int(
            meta.get("detected_speakers")
            or len({int(t.get("speaker", 0)) for t in turns})
        )
        counts = ultra_speaker_counts(turns, speakers, raw_ids or None)
        identity_meta = dict(meta.get("identity_verification") or {})
        if not identity_meta:
            identity_meta = {
                "enabled": False,
                "reason": "omitida_por_modo_ultra_rapido",
            }

        meta.update({
            "wall_seconds": max(
                float(meta.get("wall_seconds", 0.0) or 0.0),
                time.monotonic() - start,
            ),
            "ultra_fast_mode": True,
            "ultra_quality_mode": quality,
            "ultra_variant": "quality_90s" if quality else "max_speed",
            "ultra_strategy": (
                "one_pass_word_alignment_identity_lite"
                if quality else "one_pass_segment_alignment"
            ),
            "ultra_tradeoffs": ultra_tradeoffs(profile_name),
            "raw_sherpa_selected_speakers": raw_count,
            "detected_speakers": identity_count,
            "detected_speakers_engine": identity_count,
            "text_assigned_speakers": len(speakers),
            "assigned_raw_speaker_ids": sorted({
                int(s.get("raw_numeric_id")) for s in speakers
                if s.get("raw_numeric_id") is not None
            }),
            "passes": 1,
            "retry": False,
            "retry_requested": False,
            "retry_avoided": False,
            "retry_skipped_budget": False,
            "selection_reason": (
                "ultra_calidad_una_pasada" if quality else "ultra_una_pasada"
            ),
            "selected_threshold": None if ns >= 0 else threshold,
            "identity_verification": identity_meta,
            "identity_consistency": meta.get("identity_consistency") or {},
            "identity_refinement": meta.get("identity_refinement") or {},
            "identity_local_scan": meta.get("identity_local_scan") or {},
            "identity_wall_seconds": float(meta.get("identity_wall_seconds", 0.0) or 0.0),
            "alignment": align_meta,
            "word_timestamps_forced_for_diarization": bool(
                getattr(self, "_v5_forced_words_run", False)
            ),
            "speaker_counts": counts,
            "selective_reasr": {
                "enabled": False,
                "reason": "pendiente_benchmark_real_antes_de_gastar_presupuesto",
            },
        })
        requested = None if mode == "Auto" else int(mode)
        meta["speaker_count_validation"] = validation52.evaluar(
            meta,
            acoustic_clusters=raw_count,
            identity_clusters=identity_count,
            text_speakers=len(speakers),
            unassigned_raw_ids=counts["unassigned_raw_ids"],
            manual_requested=requested,
        )
        if mode == "Auto":
            meta["speaker_count_validation"]["ambiguous"] = True
            meta["speaker_count_validation"]["ultra_fast_limited"] = True
            meta["speaker_count_validation"]["status"] = (
                "estimacion_ultra_calidad_una_pasada"
                if quality else "estimacion_ultra_una_pasada"
            )

        internal = meta.get("sherpa_internal") or {}
        if quality:
            log(
                "Ultra Calidad: una sola pasada sherpa + alineación palabra↔hablante · "
                f"{raw_count} cluster(s) sherpa → {identity_count} tras identidad ligera · "
                f"{len(speakers)} con texto · "
                f"{int(align_meta.get('speaker_switches_inside_segments', 0) or 0)} "
                "cambio(s) interno(s)."
            )
        else:
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
        quality = bool(diar_meta.get("ultra_quality_mode", False))
        m.update({
            "ultra_fast_mode": True,
            "ultra_quality_mode": quality,
            "ultra_variant": "quality_90s" if quality else "max_speed",
            "ultra_one_pass": True,
            "ultra_auto_threshold": ULTRA_AUTO_THRESHOLD,
            "ultra_alignment": "word_level" if quality else "segment_overlap",
            "ultra_identity_verification": bool(
                (diar_meta.get("identity_verification") or {}).get("enabled", False)
            ),
            "ultra_tradeoffs": diar_meta.get("ultra_tradeoffs") or ultra_tradeoffs(
                ULTRA_QUALITY_PROFILE_NAME if quality else ULTRA_PROFILE_NAME
            ),
            "selective_reasr": diar_meta.get("selective_reasr") or {
                "enabled": False,
                "reason": "pendiente_benchmark_real_antes_de_gastar_presupuesto",
            },
        })
        return self._recalcular_metricas_finales(m)
