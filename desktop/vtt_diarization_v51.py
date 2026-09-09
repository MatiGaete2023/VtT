#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Diarización V5.1: consistencia de identidad y escaneo local conservador."""
from __future__ import annotations

import time
from typing import Callable, Dict, Optional, Sequence

import numpy as np

import vtt_diarization as legacy
import vtt_diarization_v5 as v5
import vtt_identity as identity


class DiarizationEngine(v5.DiarizationEngine):
    """Extiende V5 sin repetir la diarización principal."""

    def __init__(self, carpeta_modelos):
        super().__init__(carpeta_modelos)
        self.identity_extractor = None
        self.identity_extractor_init_seconds = 0.0

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

    def diarize(
        self, ruta: str, *, num_speakers: int = -1, threshold: float = 0.5,
        log: Optional[Callable[[str], None]] = None,
        progreso: Optional[Callable[[float], None]] = None,
        speech_regions: Optional[Sequence[Sequence[float]]] = None,
        adaptive: bool = False, diar_profile: str = "Equilibrada",
    ):
        log = log or (lambda _: None)
        progreso = progreso or (lambda _: None)
        turnos, meta = super().diarize(
            ruta, num_speakers=num_speakers, threshold=threshold,
            log=log, progreso=progreso, speech_regions=speech_regions,
            adaptive=adaptive, diar_profile=diar_profile,
        )
        meta = dict(meta or {})
        if not turnos:
            meta["identity_verification"] = {"enabled": False, "reason": "sin_turnos"}
            return turnos, meta

        t_all = time.perf_counter()
        t_decode = time.perf_counter()
        audio = legacy.decodificar_audio_mono(ruta, 16000)
        identity_decode_seconds = time.perf_counter() - t_decode
        extractor, extractor_reused, extractor_init = self._ensure_identity_extractor()

        cache: Dict[tuple, object] = {}
        embed_calls = cache_hits = 0
        compute_seconds = 0.0

        def embed_interval(a: float, b: float):
            nonlocal embed_calls, cache_hits, compute_seconds
            a = max(0.0, float(a)); b = max(a, float(b))
            key = (round(a, 3), round(b, 3))
            if key in cache:
                cache_hits += 1
                return cache[key]
            ia, ib = max(0, int(a * 16000)), min(len(audio), int(b * 16000))
            if ib - ia < int(identity.MIN_EMBED_SECONDS * 16000):
                cache[key] = None
                return None
            stream = extractor.create_stream()
            stream.accept_waveform(
                sample_rate=16000,
                waveform=np.ascontiguousarray(audio[ia:ib], dtype=np.float32),
            )
            stream.input_finished()
            if not extractor.is_ready(stream):
                cache[key] = None
                return None
            t0 = time.perf_counter()
            value = identity.normalizar(extractor.compute(stream))
            compute_seconds += time.perf_counter() - t0
            embed_calls += 1
            cache[key] = value
            return value

        emb0, extract0 = identity.extraer_embeddings_turnos(turnos, embed_interval)
        is_auto = bool(adaptive and num_speakers < 0)
        if is_auto:
            refined, refine_meta = identity.refinar_turnos(turnos, emb0, allow_new_identities=True)
        else:
            refined = [dict(t) for t in turnos]
            n0 = len({int(t["speaker"]) for t in turnos})
            refine_meta = {
                "skipped": True, "reason": "conteo_manual_preserva_identidades_sherpa",
                "speakers_before": n0, "speakers_after": n0,
                "reassigned_turns": 0, "new_identities": 0,
            }

        local_enabled = bool(
            is_auto and any(
                float(t.get("end", 0.0)) - float(t.get("start", 0.0))
                >= identity.LOCAL_SCAN_MIN_SECONDS for t in refined
            )
        )
        scanned, scan_meta = identity.escanear_cambios_locales(
            refined, embed_interval, allow_new_identities=is_auto,
            enabled=local_enabled,
        )
        final_emb, extract_final = identity.extraer_embeddings_turnos(scanned, embed_interval)
        consistency = identity.resumir_identidades(scanned, final_emb)
        identity_wall = time.perf_counter() - t_all
        meta["identity_verification"] = {
            "enabled": True,
            "calibration": {
                "same_speaker_pair_floor_observed": 0.45,
                "different_speaker_pair_ceiling_observed": 0.33,
                "source": "official_sherpa_2_and_4_speaker_test_audio",
                "note": "referencias de calibración, no umbrales biométricos universales",
            },
            "extractor_reused": bool(extractor_reused),
            "extractor_init_seconds": float(extractor_init),
            "audio_decode_seconds": float(identity_decode_seconds),
            "embedding_compute_seconds": float(compute_seconds),
            "embedding_calls": int(embed_calls),
            "embedding_cache_hits": int(cache_hits),
            "initial_extraction": extract0, "final_extraction": extract_final,
            "refinement": refine_meta, "local_scan": scan_meta,
            "consistency": consistency, "wall_seconds": float(identity_wall),
        }
        meta["identity_refinement"] = refine_meta
        meta["identity_local_scan"] = scan_meta
        meta["identity_consistency"] = consistency
        meta["identity_wall_seconds"] = float(identity_wall)
        meta["detected_speakers_before_identity"] = len({int(t["speaker"]) for t in turnos})
        meta["detected_speakers"] = len({int(t["speaker"]) for t in scanned})
        log(
            "V5.1 identidad: "
            f"{meta['detected_speakers_before_identity']} → {meta['detected_speakers']} hablante(s) · "
            f"consistencia {consistency.get('overall_confidence', 'sin_datos')} · "
            f"{int(scan_meta.get('applied_changes', 0) or 0)} cambio(s) local(es)."
        )
        return scanned, meta
