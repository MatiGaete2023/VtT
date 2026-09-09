#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Diarización V5: motor persistente, reutilización de modelos y tiempos internos.

Desde V5.2 expone hooks conservadores para que capas posteriores puedan intentar
un precheck acústico antes de pagar una segunda pasada completa de sherpa y
participar en la selección de candidatos sin romper el comportamiento V5/V5.1.
"""
from __future__ import annotations

import os
import re
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import vtt_diarization as legacy
import vtt_diarization_adaptive as v3
import vtt_diarization_v4 as v4


_TIMING_PATTERNS = {
    "segmentation_seconds": re.compile(r"OfflineSpeakerDiarization:\s*segmentation\s+([0-9]+(?:\.[0-9]+)?)\s+s", re.I),
    "embedding_seconds": re.compile(r"OfflineSpeakerDiarization:\s*embedding\s+([0-9]+(?:\.[0-9]+)?)\s+s", re.I),
    "clustering_seconds": re.compile(r"OfflineSpeakerDiarization:\s*clustering\s+([0-9]+(?:\.[0-9]+)?)\s+s", re.I),
    "sherpa_total_seconds": re.compile(r"OfflineSpeakerDiarization:\s*total\s+([0-9]+(?:\.[0-9]+)?)\s+s", re.I),
    "sherpa_rtf": re.compile(r"OfflineSpeakerDiarization:\s*total\s+[0-9]+(?:\.[0-9]+)?\s+s,\s*audio\s+[0-9]+(?:\.[0-9]+)?\s+s,\s*RTF\s+([0-9]+(?:\.[0-9]+)?)", re.I),
}


def parse_sherpa_timings(text: str) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for key, pat in _TIMING_PATTERNS.items():
        matches = pat.findall(text or "")
        if matches:
            out[key] = float(matches[-1])
    return out


def _config(sherpa, seg_model: Path, emb_model: Path, num_speakers: int,
            threshold: float, threads: int, shift: float, *, debug: bool = True):
    return sherpa.OfflineSpeakerDiarizationConfig(
        segmentation=sherpa.OfflineSpeakerSegmentationModelConfig(
            pyannote=sherpa.OfflineSpeakerSegmentationPyannoteModelConfig(
                model=str(seg_model), window_shift_ratio=float(shift)
            ),
            num_threads=int(threads), debug=bool(debug), provider="cpu",
        ),
        embedding=sherpa.SpeakerEmbeddingExtractorConfig(
            model=str(emb_model), num_threads=int(threads)
        ),
        clustering=sherpa.FastClusteringConfig(
            num_clusters=int(num_speakers), threshold=float(threshold)
        ),
        min_duration_on=0.3, min_duration_off=0.5,
    )


def _capture_native_stderr(callable_):
    saved = None; tmp = None; captured = ""
    try:
        try: sys.stderr.flush()
        except Exception: pass
        saved = os.dup(2)
        tmp = tempfile.TemporaryFile(mode="w+b")
        os.dup2(tmp.fileno(), 2)
    except Exception:
        if saved is not None:
            try: os.close(saved)
            except Exception: pass
        if tmp is not None:
            try: tmp.close()
            except Exception: pass
        return callable_(), ""

    error = None; result = None
    try:
        result = callable_()
        try: sys.stderr.flush()
        except Exception: pass
    except BaseException as exc:
        error = exc
    finally:
        try: os.dup2(saved, 2)
        finally:
            try: os.close(saved)
            except Exception: pass
    try:
        tmp.seek(0)
        captured = tmp.read().decode("utf-8", errors="replace")
    finally:
        tmp.close()
    if error is not None:
        raise error
    return result, captured


class DiarizationEngine:
    """Motor secuencial reutilizable dentro de un worker persistente."""

    def __init__(self, carpeta_modelos: Path):
        self.carpeta_modelos = Path(carpeta_modelos)
        self.sherpa = None
        self.seg_model: Optional[Path] = None
        self.emb_model: Optional[Path] = None
        self.threads: Optional[int] = None
        self.sd = None
        self.sd_shift: Optional[float] = None
        self.jobs = 0
        self.model_prepare_total = 0.0
        self.engine_init_total = 0.0
        self._last_decoded_audio = None
        self._last_decoded_audio_rate = None
        self._last_decoded_audio_path = None

    def _ensure_models(self, log: Callable[[str], None]) -> Dict[str, Any]:
        meta = {
            "models_reused": self.seg_model is not None and self.emb_model is not None,
            "model_prepare_seconds": 0.0,
        }
        if self.sherpa is None:
            import sherpa_onnx as sherpa
            self.sherpa = sherpa
        if self.seg_model is None or self.emb_model is None:
            t0 = time.perf_counter()
            self.seg_model, self.emb_model = legacy.asegurar_modelos(self.carpeta_modelos, log)
            meta["model_prepare_seconds"] = time.perf_counter() - t0
            self.model_prepare_total += meta["model_prepare_seconds"]
        if self.threads is None:
            self.threads = v3.hilos_diarizacion()
        return meta

    def _engine(self, *, num_speakers: int, threshold: float, shift: float) -> Tuple[Any, Dict[str, Any]]:
        sherpa = self.sherpa
        assert sherpa is not None and self.seg_model is not None and self.emb_model is not None
        cfg = _config(
            sherpa, self.seg_model, self.emb_model, num_speakers, threshold,
            int(self.threads or 1), shift, debug=True,
        )
        if not cfg.validate():
            raise RuntimeError("Configuración de diarización inválida; revisa los modelos")
        meta = {
            "engine_reused": self.sd is not None and self.sd_shift == float(shift),
            "engine_init_seconds": 0.0,
            "clustering_config_seconds": 0.0,
        }
        if self.sd is None or self.sd_shift != float(shift):
            t0 = time.perf_counter()
            self.sd = sherpa.OfflineSpeakerDiarization(cfg)
            meta["engine_init_seconds"] = time.perf_counter() - t0
            self.engine_init_total += meta["engine_init_seconds"]
            self.sd_shift = float(shift)
        else:
            t0 = time.perf_counter(); self.sd.set_config(cfg)
            meta["clustering_config_seconds"] = time.perf_counter() - t0
        return self.sd, meta

    def _process(self, sd, audio, progreso: Callable[[float], None], p0: float, p1: float) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        span = max(0.0, float(p1) - float(p0))
        def callback(done: int, total: int) -> int:
            if total:
                frac = min(1.0, max(0.0, float(done) / float(total)))
                progreso(float(p0) + span * frac)
            return 0
        t0 = time.perf_counter()
        result, native_log = _capture_native_stderr(
            lambda: sd.process(audio, callback=callback).sort_by_start_time()
        )
        wall = time.perf_counter() - t0
        progreso(float(p1))
        turnos = [
            {"start": float(x.start), "end": float(x.end), "speaker": int(x.speaker)}
            for x in result if float(x.end) > float(x.start)
        ]
        internal = parse_sherpa_timings(native_log)
        return turnos, {
            "process_wall_seconds": wall, "internal": internal,
            "internal_timing_available": bool(internal),
        }

    # Hooks V5.2. Las implementaciones anteriores conservan el comportamiento
    # original porque por defecto no hacen precheck ni cambian la selección.
    def _auto_pre_retry(self, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return None

    def _auto_choose_candidates(
        self,
        first: Tuple[List[Dict[str, Any]], Dict[str, Any]],
        second: Tuple[List[Dict[str, Any]], Dict[str, Any]],
        reason: str,
        context: Dict[str, Any],
    ):
        turnos, analysis, why = v4.elegir_candidato(first, second, reason)
        return turnos, analysis, why, {}

    def diarize(self, ruta: str, *, num_speakers: int = -1, threshold: float = 0.5,
                log: Optional[Callable[[str], None]] = None,
                progreso: Optional[Callable[[float], None]] = None,
                speech_regions: Optional[Sequence[Sequence[float]]] = None,
                adaptive: bool = False,
                diar_profile: str = "Equilibrada") -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        log = log or (lambda _: None); progreso = progreso or (lambda _: None)
        self.jobs += 1
        prep = self._ensure_models(log)
        nombre_perfil, cfg_perfil = v4.perfil_diarizacion(diar_profile)
        shift = float(cfg_perfil["window_shift_ratio"])
        initial_th = v4.AUTO_INITIAL_THRESHOLD if adaptive and num_speakers < 0 else float(threshold)
        sd, engine_meta = self._engine(num_speakers=num_speakers, threshold=initial_th, shift=shift)
        progreso(2.0)

        t_decode = time.perf_counter(); log("Decodificando audio para identificar hablantes…")
        original = legacy.decodificar_audio_mono(ruta, int(sd.sample_rate))
        decode_seconds = time.perf_counter() - t_decode
        sr = int(sd.sample_rate); audio_seconds = len(original) / sr if sr else 0.0
        # V5.1/V5.2 pueden reutilizar este PCM y evitar una segunda decodificación.
        self._last_decoded_audio = original
        self._last_decoded_audio_rate = sr
        self._last_decoded_audio_path = str(ruta)
        progreso(5.0)

        t_reduce = time.perf_counter()
        audio, mapa, reduccion = v3._reducir(original, sr, speech_regions or [])
        reduction_seconds = time.perf_counter() - t_reduce
        if reduccion.get("enabled"):
            log(f"Diarización sobre regiones de voz: {reduccion['coverage']*100:.0f}% del audio ({reduccion['regions']} regiones).")
        else:
            log("Diarización sobre audio completo (sin ahorro seguro por regiones).")
        log(f"Perfil de diarización {nombre_perfil}: window shift {shift:.2f} · {int(self.threads or 1)} hilo(s) · worker persistente job {self.jobs}.")
        if engine_meta["engine_reused"]:
            log("Modelos de diarización reutilizados desde el worker persistente.")
        else:
            log(f"Motor de diarización inicializado en {engine_meta['engine_init_seconds']:.2f} s.")

        meta: Dict[str, Any] = {
            "adaptive": bool(adaptive and num_speakers < 0),
            "requested_speakers": None if num_speakers < 0 else int(num_speakers),
            "speech_region_reduction": reduccion, "selected_threshold": None,
            "retry": False, "retry_requested": False, "retry_avoided": False,
            "passes": 1, "num_threads": int(self.threads or 1),
            "diarization_profile": nombre_perfil, "window_shift_ratio": shift,
            "selection_reason": "manual" if num_speakers >= 0 else "primera_pasada_estable",
            "candidates": [], "worker_job_index": self.jobs,
            "models_reused": bool(prep["models_reused"]),
            "model_prepare_seconds": float(prep["model_prepare_seconds"]),
            "engine_reused": bool(engine_meta["engine_reused"]),
            "engine_init_seconds": float(engine_meta["engine_init_seconds"]),
            "clustering_config_seconds": float(engine_meta["clustering_config_seconds"]),
            "decode_seconds": decode_seconds, "reduction_seconds": reduction_seconds,
            "sherpa_pass_timings": [],
        }

        if adaptive and num_speakers < 0:
            meta["selected_threshold"] = initial_th
            log(f"Auto: primera pasada (umbral {initial_th:.2f}).")
            turnos_a_raw, timing_a = self._process(sd, audio, progreso, 5.0, 50.0)
            turnos_a = v3._remap(turnos_a_raw, mapa)
            a = v4.analizar_turnos(turnos_a, audio_seconds)
            meta["sherpa_pass_timings"].append({"pass": 1, **timing_a})
            meta["candidates"].append({"threshold": initial_th, "analysis": a})
            retry_th, motivo = v4.decidir_reintento(a)

            if retry_th is not None:
                meta["retry_requested"] = True
                hook_context = {
                    "ruta": str(ruta), "original_audio": original, "sample_rate": sr,
                    "audio_seconds": audio_seconds, "first_turns": turnos_a,
                    "first_analysis": a, "initial_threshold": initial_th,
                    "retry_threshold": retry_th, "retry_reason": motivo,
                    "diarization_profile": nombre_perfil,
                }
                pre = self._auto_pre_retry(hook_context) or {}
                if pre:
                    meta["auto_precheck"] = dict(pre.get("meta") or {})
                if bool(pre.get("accepted")):
                    turnos = [dict(t) for t in (pre.get("turns") or turnos_a)]
                    elegido = dict(pre.get("analysis") or v4.analizar_turnos(turnos, audio_seconds))
                    meta["retry_avoided"] = True
                    meta["retry_reason"] = motivo
                    meta["selection_reason"] = str(pre.get("selection_reason") or "precheck_identidad_evito_segunda_pasada")
                    meta["selected_analysis"] = elegido
                    meta["candidates"][0]["precheck"] = dict(pre.get("meta") or {})
                    progreso(100.0)
                    log("Auto: precheck acústico aceptó la primera pasada refinada; se evita repetir sherpa completo.")
                else:
                    meta["retry"] = True; meta["passes"] = 2
                    log(f"Auto: resultado estructuralmente sospechoso ({motivo}); segunda pasada con umbral {retry_th:.2f}.")
                    sd2, cfg_meta2 = self._engine(num_speakers=-1, threshold=retry_th, shift=shift)
                    meta["clustering_config_seconds"] += float(cfg_meta2.get("clustering_config_seconds", 0.0))
                    turnos_b_raw, timing_b = self._process(sd2, audio, progreso, 50.0, 100.0)
                    turnos_b = v3._remap(turnos_b_raw, mapa)
                    b = v4.analizar_turnos(turnos_b, audio_seconds)
                    meta["sherpa_pass_timings"].append({"pass": 2, **timing_b})
                    meta["candidates"].append({"threshold": retry_th, "analysis": b})
                    choose_context = dict(hook_context)
                    choose_context.update({"second_turns": turnos_b, "second_analysis": b})
                    turnos, elegido, razon, extra = self._auto_choose_candidates(
                        (turnos_a, a), (turnos_b, b), motivo, choose_context
                    )
                    if turnos is turnos_b:
                        meta["selected_threshold"] = retry_th
                    meta["selection_reason"] = razon; meta["retry_reason"] = motivo
                    meta["selected_analysis"] = elegido
                    meta["stability_delta_speakers"] = abs(int(a.get("speaker_count", 0)) - int(b.get("speaker_count", 0)))
                    if extra:
                        meta["identity_aware_selection"] = dict(extra)
            else:
                progreso(100.0); turnos = turnos_a; meta["selected_analysis"] = a
        else:
            meta["selected_threshold"] = None if num_speakers >= 0 else float(threshold)
            turnos_raw, timing = self._process(sd, audio, progreso, 5.0, 100.0)
            turnos = v3._remap(turnos_raw, mapa)
            meta["sherpa_pass_timings"].append({"pass": 1, **timing})
            analisis = v4.analizar_turnos(turnos, audio_seconds)
            meta["selected_analysis"] = analisis
            meta["candidates"].append({"threshold": meta["selected_threshold"], "analysis": analisis})

        sums = {"segmentation_seconds": 0.0, "embedding_seconds": 0.0,
                "clustering_seconds": 0.0, "sherpa_total_seconds": 0.0}
        available = False; process_wall = 0.0
        for p in meta["sherpa_pass_timings"]:
            process_wall += float(p.get("process_wall_seconds", 0.0) or 0.0)
            internal = p.get("internal") or {}; available = available or bool(internal)
            for key in sums:
                sums[key] += float(internal.get(key, 0.0) or 0.0)
        meta["sherpa_internal_timing_available"] = available
        meta["sherpa_internal"] = sums
        meta["sherpa_process_wall_seconds"] = process_wall
        meta["detected_speakers"] = len({int(t["speaker"]) for t in turnos})
        meta["turns"] = len(turnos)
        progreso(100.0)
        return turnos, meta
