#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Diarización V5.2-performance.

Objetivos:
- intentar resolver sobredetección con embeddings baratos antes de repetir
  sherpa completo;
- usar consistencia de identidad cuando dos candidatos Auto siguen ambiguos;
- reutilizar PCM, extractor y embeddings durante todo el job;
- mantener un presupuesto acotado para el precheck.
"""
from __future__ import annotations

import time
from typing import Any, Callable, Dict, Optional, Sequence

import numpy as np

import vtt_diarization_v4 as v4
import vtt_diarization_v5 as v5
import vtt_identity_v52 as identity


PRECHECK_MAX_EMBEDDINGS = 18
PRECHECK_MAX_PER_SPEAKER = 3
PRECHECK_ACCEPT_PENALTY = 2.60
IDENTITY_AWARE_STRUCTURAL_THRESHOLD = 2.0
IDENTITY_AWARE_CLOSE_SCORE = 1.0


def selected_raw_candidate(meta: Dict[str, Any]) -> Dict[str, Any]:
    """Determina qué candidato sherpa originó la solución seleccionada.

    V5.2 puede devolver una lista refinada distinta por identidad, por lo que
    ya no es fiable decidir por identidad de objeto (``turnos is turnos_b``).
    La trazabilidad se resuelve con la razón/selección explícita y los
    candidatos guardados por V5.
    """
    candidates = list(meta.get("candidates") or [])
    selected = "first"
    aware = dict(meta.get("identity_aware_selection") or {})
    aware_choice = str(aware.get("selected_candidate") or "")
    reason = str(meta.get("selection_reason") or "")

    if aware_choice in {"first", "second"}:
        selected = aware_choice
    elif bool(meta.get("retry_avoided")):
        selected = "first"
    elif reason in {
        "segunda_pasada_mejora_estructura",
        "seleccion_identity_aware_second",
    }:
        selected = "second"
    elif reason in {
        "se_conserva_primera_pasada",
        "primera_pasada_estable",
        "precheck_identidad_evito_segunda_pasada",
        "seleccion_identity_aware_first",
    }:
        selected = "first"
    elif bool(meta.get("retry")) and len(candidates) > 1:
        # Fallback conservador para metadatos antiguos: el threshold elegido
        # permite identificar la segunda pasada sin comparar listas Python.
        try:
            chosen_th = float(meta.get("selected_threshold"))
            second_th = float(candidates[1].get("threshold"))
            if abs(chosen_th - second_th) < 1e-9:
                selected = "second"
        except (TypeError, ValueError, IndexError):
            pass

    idx = 1 if selected == "second" else 0
    candidate = candidates[idx] if idx < len(candidates) else {}
    analysis = dict(candidate.get("analysis") or {})
    try:
        count = int(analysis.get("speaker_count", 0) or 0)
    except (TypeError, ValueError):
        count = 0
    threshold = candidate.get("threshold")
    return {
        "candidate": selected,
        "index": idx,
        "speaker_count": count,
        "threshold": threshold,
    }


class DiarizationEngine(v5.DiarizationEngine):
    def __init__(self, carpeta_modelos):
        super().__init__(carpeta_modelos)
        self.identity_extractor = None
        self.identity_extractor_init_seconds = 0.0
        self._v52_runtime = None
        self._v52_first_precheck = None

    def _ensure_identity_extractor(self):
        if self.identity_extractor is not None:
            return self.identity_extractor, True, 0.0
        assert self.sherpa is not None and self.emb_model is not None
        cfg = self.sherpa.SpeakerEmbeddingExtractorConfig(
            model=str(self.emb_model), num_threads=int(self.threads or 1),
            debug=False, provider="cpu",
        )
        if not cfg.validate():
            raise RuntimeError("Configuración de embeddings de identidad inválida")
        t0 = time.perf_counter()
        self.identity_extractor = self.sherpa.SpeakerEmbeddingExtractor(cfg)
        elapsed = time.perf_counter() - t0
        self.identity_extractor_init_seconds += elapsed
        return self.identity_extractor, False, elapsed

    def _runtime(self, context: Dict[str, Any]):
        ruta = str(context.get("ruta", ""))
        sr = int(context.get("sample_rate", 0) or 0)
        audio = context.get("original_audio")
        current = self._v52_runtime
        if current is not None and current.get("ruta") == ruta and current.get("audio") is audio:
            return current
        if audio is None or sr != 16000:
            return None
        extractor, reused, init_seconds = self._ensure_identity_extractor()
        rt = {
            "ruta": ruta, "audio": audio, "sample_rate": sr,
            "extractor": extractor, "extractor_reused": bool(reused),
            "extractor_init_seconds": float(init_seconds), "cache": {},
            "embedding_calls": 0, "cache_hits": 0, "compute_seconds": 0.0,
        }
        self._v52_runtime = rt
        return rt

    @staticmethod
    def _embedder(rt):
        def embed_interval(a: float, b: float):
            a = max(0.0, float(a)); b = max(a, float(b))
            key = (round(a, 3), round(b, 3))
            cache = rt["cache"]
            if key in cache:
                rt["cache_hits"] += 1
                return cache[key]
            audio = rt["audio"]
            ia = max(0, int(a * 16000)); ib = min(len(audio), int(b * 16000))
            if ib - ia < int(identity.MIN_EMBED_SECONDS * 16000):
                cache[key] = None; return None
            stream = rt["extractor"].create_stream()
            stream.accept_waveform(
                sample_rate=16000,
                waveform=np.ascontiguousarray(audio[ia:ib], dtype=np.float32),
            )
            stream.input_finished()
            if not rt["extractor"].is_ready(stream):
                cache[key] = None; return None
            t0 = time.perf_counter()
            value = identity.normalizar(rt["extractor"].compute(stream))
            rt["compute_seconds"] += time.perf_counter() - t0
            rt["embedding_calls"] += 1
            cache[key] = value
            return value
        return embed_interval

    def _light_identity(self, turnos, context, *, max_total=PRECHECK_MAX_EMBEDDINGS):
        rt = self._runtime(context)
        if rt is None:
            return None
        t0 = time.perf_counter(); before_calls = int(rt["embedding_calls"])
        embed = self._embedder(rt)
        embeddings, extraction = identity.extraer_embeddings_turnos(
            turnos, embed, max_per_speaker=PRECHECK_MAX_PER_SPEAKER,
            max_total=int(max_total),
        )
        refined, refinement = identity.refinar_turnos(
            turnos, embeddings, allow_new_identities=True
        )
        consistency = identity.resumir_identidades(refined, embeddings)
        analysis = v4.analizar_turnos(
            refined, float(context.get("audio_seconds", 0.0) or 0.0)
        )
        return {
            "turns": refined, "analysis": analysis, "consistency": consistency,
            "identity_penalty": identity.identity_penalty(consistency),
            "extraction": extraction, "refinement": refinement,
            "wall_seconds": time.perf_counter() - t0,
            "new_embedding_calls": int(rt["embedding_calls"]) - before_calls,
        }

    def _auto_pre_retry(self, context: Dict[str, Any]):
        reason = str(context.get("retry_reason") or "")
        if reason not in {"sobredeteccion_extrema", "fragmentacion_excesiva"}:
            return {
                "accepted": False,
                "meta": {"enabled": False, "reason": "precheck_no_aplicable"},
            }
        result = self._light_identity(context["first_turns"], context)
        if result is None:
            return {
                "accepted": False,
                "meta": {"enabled": False, "reason": "audio_no_reutilizable"},
            }
        self._v52_first_precheck = result
        before_n = int(context["first_analysis"].get("speaker_count", 0) or 0)
        after_n = int(result["analysis"].get("speaker_count", 0) or 0)
        penalty = float(result["analysis"].get("penalty", 0.0) or 0.0)
        low = int(result["consistency"].get("low_confidence_speakers", 0) or 0)
        accepted = bool(
            2 <= after_n <= v4.AUTO_MAX_SPEAKERS
            and after_n < before_n
            and penalty <= PRECHECK_ACCEPT_PENALTY
            and low == 0
        )
        meta = {
            "enabled": True, "accepted": accepted,
            "speakers_before": before_n, "speakers_after": after_n,
            "structural_penalty": penalty,
            "identity_penalty": float(result["identity_penalty"]),
            "identity_confidence": result["consistency"].get("overall_confidence"),
            "wall_seconds": float(result["wall_seconds"]),
            "embedding_calls": int(result["new_embedding_calls"]),
            "refinement": result["refinement"], "extraction": result["extraction"],
            "budget_max_embeddings": PRECHECK_MAX_EMBEDDINGS,
        }
        return {
            "accepted": accepted, "turns": result["turns"],
            "analysis": result["analysis"], "meta": meta,
            "selection_reason": "precheck_identidad_evito_segunda_pasada",
        }

    def _auto_choose_candidates(self, first, second, reason, context):
        struct_turns, struct_analysis, struct_reason = v4.elegir_candidato(
            first, second, reason
        )
        a = first[1]; b = second[1]
        structural_gap = abs(
            float(a.get("penalty", 0.0)) - float(b.get("penalty", 0.0))
        )
        selected_penalty = float(struct_analysis.get("penalty", 0.0) or 0.0)
        need_identity = bool(
            selected_penalty >= IDENTITY_AWARE_STRUCTURAL_THRESHOLD
            or structural_gap <= IDENTITY_AWARE_CLOSE_SCORE
        )
        if not need_identity:
            return struct_turns, struct_analysis, struct_reason, {
                "enabled": False, "reason": "diferencia_estructural_suficiente",
                "selected_candidate": "second" if struct_turns is second[0] else "first",
            }

        first_id = self._v52_first_precheck or self._light_identity(first[0], context)
        second_id = self._light_identity(second[0], context)
        if first_id is None or second_id is None:
            return struct_turns, struct_analysis, struct_reason, {
                "enabled": False, "reason": "identidad_no_disponible",
                "selected_candidate": "second" if struct_turns is second[0] else "first",
            }
        score_a = (
            float(first_id["analysis"].get("penalty", 0.0))
            + float(first_id["identity_penalty"])
        )
        score_b = (
            float(second_id["analysis"].get("penalty", 0.0))
            + float(second_id["identity_penalty"])
        )
        if score_b + 0.15 < score_a:
            chosen, which = second_id, "second"
        elif score_a + 0.15 < score_b:
            chosen, which = first_id, "first"
        else:
            which = "second" if struct_turns is second[0] else "first"
            chosen = second_id if which == "second" else first_id
        extra = {
            "enabled": True, "selected_candidate": which,
            "first_score": score_a, "second_score": score_b,
            "first_structural_penalty": float(first_id["analysis"].get("penalty", 0.0)),
            "second_structural_penalty": float(second_id["analysis"].get("penalty", 0.0)),
            "first_identity_penalty": float(first_id["identity_penalty"]),
            "second_identity_penalty": float(second_id["identity_penalty"]),
            "first_identity_confidence": first_id["consistency"].get("overall_confidence"),
            "second_identity_confidence": second_id["consistency"].get("overall_confidence"),
        }
        return (
            chosen["turns"], chosen["analysis"],
            f"seleccion_identity_aware_{which}", extra,
        )

    def diarize(
        self, ruta: str, *, num_speakers: int = -1, threshold: float = 0.5,
        log: Optional[Callable[[str], None]] = None,
        progreso: Optional[Callable[[float], None]] = None,
        speech_regions: Optional[Sequence[Sequence[float]]] = None,
        adaptive: bool = False, diar_profile: str = "Equilibrada",
    ):
        log = log or (lambda _: None); progreso = progreso or (lambda _: None)
        self._v52_runtime = None; self._v52_first_precheck = None
        turnos, meta = super().diarize(
            ruta, num_speakers=num_speakers, threshold=threshold,
            log=log, progreso=progreso, speech_regions=speech_regions,
            adaptive=adaptive, diar_profile=diar_profile,
        )
        meta = dict(meta or {})

        raw_info = selected_raw_candidate(meta)
        meta["raw_sherpa_selected_speakers"] = int(raw_info["speaker_count"])
        meta["raw_sherpa_candidate_selected"] = str(raw_info["candidate"])
        if raw_info.get("threshold") is not None:
            meta["selected_threshold"] = raw_info["threshold"]

        if not turnos:
            meta["identity_verification"] = {
                "enabled": False, "reason": "sin_turnos"
            }
            return turnos, meta

        context = {
            "ruta": str(ruta), "original_audio": self._last_decoded_audio,
            "sample_rate": int(self._last_decoded_audio_rate or 0),
            "audio_seconds": (
                len(self._last_decoded_audio) / float(self._last_decoded_audio_rate)
                if self._last_decoded_audio is not None and self._last_decoded_audio_rate
                else 0.0
            ),
        }
        rt = self._runtime(context)
        if rt is None:
            # Compatibilidad defensiva: la configuración actual de sherpa usa 16 kHz.
            import vtt_diarization as legacy
            t_dec = time.perf_counter()
            audio = legacy.decodificar_audio_mono(ruta, 16000)
            decode_seconds = time.perf_counter() - t_dec
            context.update({
                "original_audio": audio, "sample_rate": 16000,
                "audio_seconds": len(audio) / 16000.0,
            })
            rt = self._runtime(context)
        else:
            decode_seconds = 0.0
        assert rt is not None
        embed = self._embedder(rt)
        t_final = time.perf_counter(); before_final_calls = int(rt["embedding_calls"])
        emb0, extract0 = identity.extraer_embeddings_turnos(turnos, embed)
        is_auto = bool(adaptive and num_speakers < 0)
        if is_auto:
            refined, refine_meta = identity.refinar_turnos(
                turnos, emb0, allow_new_identities=True
            )
        else:
            refined = [dict(t) for t in turnos]
            n0 = len({int(t["speaker"]) for t in turnos})
            refine_meta = {
                "skipped": True,
                "reason": "conteo_manual_preserva_identidades_sherpa",
                "speakers_before": n0, "speakers_after": n0,
                "reassigned_turns": 0, "new_identities": 0,
            }
        local_enabled = bool(is_auto and any(
            float(t.get("end", 0.0)) - float(t.get("start", 0.0))
            >= identity.LOCAL_SCAN_MIN_SECONDS for t in refined
        ))
        scanned, scan_meta = identity.escanear_cambios_locales(
            refined, embed, allow_new_identities=is_auto, enabled=local_enabled
        )
        final_emb, extract_final = identity.extraer_embeddings_turnos(scanned, embed)
        consistency = identity.resumir_identidades(scanned, final_emb)
        final_wall = time.perf_counter() - t_final

        meta["identity_verification"] = {
            "enabled": True,
            "calibration": {
                "same_speaker_pair_floor_observed": 0.45,
                "different_speaker_pair_ceiling_observed": 0.33,
                "source": "official_sherpa_2_and_4_speaker_test_audio",
                "note": "referencias de calibración, no umbrales biométricos universales",
            },
            "extractor_reused": bool(rt["extractor_reused"]),
            "extractor_init_seconds": float(rt["extractor_init_seconds"]),
            "audio_decode_seconds": float(decode_seconds),
            "audio_reused_from_diarization": decode_seconds == 0.0,
            "embedding_compute_seconds": float(rt["compute_seconds"]),
            "embedding_calls": int(rt["embedding_calls"]),
            "embedding_cache_hits": int(rt["cache_hits"]),
            "final_stage_new_embedding_calls": (
                int(rt["embedding_calls"]) - before_final_calls
            ),
            "initial_extraction": extract0, "final_extraction": extract_final,
            "refinement": refine_meta, "local_scan": scan_meta,
            "consistency": consistency, "wall_seconds": float(final_wall),
            "precheck": meta.get("auto_precheck") or {},
        }
        meta["identity_refinement"] = refine_meta
        meta["identity_local_scan"] = scan_meta
        meta["identity_consistency"] = consistency
        meta["identity_wall_seconds"] = (
            float(final_wall)
            + float((meta.get("auto_precheck") or {}).get("wall_seconds", 0.0) or 0.0)
        )
        meta["detected_speakers_before_identity"] = len({
            int(t["speaker"]) for t in turnos
        })
        meta["detected_speakers"] = len({int(t["speaker"]) for t in scanned})
        log(
            "V5.2 identidad: "
            f"sherpa {meta['raw_sherpa_selected_speakers']} · "
            f"entrada refinada {meta['detected_speakers_before_identity']} → "
            f"{meta['detected_speakers']} cluster(s) · "
            f"consistencia {consistency.get('overall_confidence', 'sin_datos')} · "
            f"sonda larga {int(scan_meta.get('probe_turns', 0) or 0)} / "
            f"detalle {int(scan_meta.get('detailed_scanned_turns', 0) or 0)}."
        )
        self._last_decoded_audio = None
        self._last_decoded_audio_path = None
        self._last_decoded_audio_rate = None
        self._v52_runtime = None
        return scanned, meta
