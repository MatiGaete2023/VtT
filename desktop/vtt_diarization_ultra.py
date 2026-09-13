#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Motor de diarización Ultra: una pasada sherpa + identidad ligera opcional.

No ejecuta segunda pasada, precheck Auto ni escaneo largo. Para ``Ultra Calidad
90s`` reutiliza el PCM ya decodificado por sherpa y calcula como máximo un
pequeño número de embeddings representativos para reconciliar identidades.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Sequence

import numpy as np

import vtt_diarization_v5 as v5
import vtt_identity_v52 as identity
from vtt_ultra_config import (
    ULTRA_IDENTITY_MAX_EMBEDDINGS,
    ULTRA_IDENTITY_MAX_PER_SPEAKER,
)


class DiarizationEngine(v5.DiarizationEngine):
    def __init__(self, carpeta_modelos: Path):
        super().__init__(carpeta_modelos)
        self.identity_extractor = None
        self.identity_extractor_init_seconds = 0.0

    def _ensure_identity_extractor(self):
        if self.identity_extractor is not None:
            return self.identity_extractor, True, 0.0
        assert self.sherpa is not None and self.emb_model is not None
        cfg = self.sherpa.SpeakerEmbeddingExtractorConfig(
            model=str(self.emb_model),
            num_threads=int(self.threads or 1),
            debug=False,
            provider="cpu",
        )
        if not cfg.validate():
            raise RuntimeError("Configuración de identidad ligera inválida")
        t0 = time.perf_counter()
        self.identity_extractor = self.sherpa.SpeakerEmbeddingExtractor(cfg)
        elapsed = time.perf_counter() - t0
        self.identity_extractor_init_seconds += elapsed
        return self.identity_extractor, False, elapsed

    @staticmethod
    def _embedder(extractor, audio, sample_rate: int, stats: Dict[str, Any]):
        cache: Dict[tuple[float, float], Any] = {}

        def embed_interval(a: float, b: float):
            a = max(0.0, float(a)); b = max(a, float(b))
            key = (round(a, 3), round(b, 3))
            if key in cache:
                stats["cache_hits"] += 1
                return cache[key]
            ia = max(0, int(round(a * sample_rate)))
            ib = min(len(audio), int(round(b * sample_rate)))
            if ib - ia < int(identity.MIN_EMBED_SECONDS * sample_rate):
                cache[key] = None
                return None
            stream = extractor.create_stream()
            stream.accept_waveform(
                sample_rate=sample_rate,
                waveform=np.ascontiguousarray(audio[ia:ib], dtype=np.float32),
            )
            stream.input_finished()
            if not extractor.is_ready(stream):
                cache[key] = None
                return None
            t0 = time.perf_counter()
            value = identity.normalizar(extractor.compute(stream))
            stats["compute_seconds"] += time.perf_counter() - t0
            stats["calls"] += 1
            cache[key] = value
            return value

        return embed_interval

    def diarize(
        self,
        ruta: str,
        *,
        num_speakers: int = -1,
        threshold: float = 0.5,
        log: Optional[Callable[[str], None]] = None,
        progreso: Optional[Callable[[float], None]] = None,
        speech_regions: Optional[Sequence[Sequence[float]]] = None,
        adaptive: bool = False,
        diar_profile: str = "Ultrarrápida",
        time_budget_seconds: Optional[float] = None,
        identity_lite: bool = False,
    ):
        log = log or (lambda _: None)
        turnos, meta = super().diarize(
            ruta,
            num_speakers=num_speakers,
            threshold=threshold,
            log=log,
            progreso=progreso,
            speech_regions=speech_regions,
            adaptive=adaptive,
            diar_profile=diar_profile,
            time_budget_seconds=time_budget_seconds,
        )
        meta = dict(meta or {})
        raw_ids = sorted({int(t.get("speaker", 0)) for t in turnos})
        before = len(raw_ids)
        meta["raw_sherpa_ids"] = raw_ids
        meta["raw_sherpa_selected_speakers"] = before
        if not identity_lite or not turnos:
            meta["identity_verification"] = {
                "enabled": False,
                "reason": "omitida_por_modo_ultra_rapido" if not identity_lite else "sin_turnos",
            }
            meta["identity_wall_seconds"] = 0.0
            meta["detected_speakers_before_identity"] = before
            meta["detected_speakers"] = before
            return turnos, meta

        audio = self._last_decoded_audio
        sample_rate = int(self._last_decoded_audio_rate or 0)
        if audio is None or sample_rate <= 0:
            meta["identity_verification"] = {
                "enabled": False,
                "reason": "pcm_no_disponible",
            }
            meta["identity_wall_seconds"] = 0.0
            meta["detected_speakers_before_identity"] = before
            meta["detected_speakers"] = before
            return turnos, meta

        t0 = time.perf_counter()
        extractor, reused, init_seconds = self._ensure_identity_extractor()
        stats = {"calls": 0, "cache_hits": 0, "compute_seconds": 0.0}
        embed = self._embedder(extractor, audio, sample_rate, stats)
        embeddings, extraction = identity.extraer_embeddings_turnos(
            turnos,
            embed,
            max_per_speaker=ULTRA_IDENTITY_MAX_PER_SPEAKER,
            max_total=ULTRA_IDENTITY_MAX_EMBEDDINGS,
        )
        # Conservador: puede reconciliar clusters existentes, pero no inventa
        # nuevas identidades y no ejecuta el costoso escaneo de turnos largos.
        refined, refinement = identity.refinar_turnos(
            turnos,
            embeddings,
            allow_new_identities=False,
        )
        consistency = identity.resumir_identidades(refined, embeddings)
        wall = time.perf_counter() - t0
        after = len({int(t.get("speaker", 0)) for t in refined})
        meta["identity_verification"] = {
            "enabled": True,
            "mode": "ultra_lite",
            "max_embeddings": ULTRA_IDENTITY_MAX_EMBEDDINGS,
            "max_per_speaker": ULTRA_IDENTITY_MAX_PER_SPEAKER,
            "extractor_reused": bool(reused),
            "extractor_init_seconds": float(init_seconds),
            "audio_reused_from_diarization": True,
            "embedding_compute_seconds": float(stats["compute_seconds"]),
            "embedding_calls": int(stats["calls"]),
            "embedding_cache_hits": int(stats["cache_hits"]),
            "extraction": extraction,
            "refinement": refinement,
            "consistency": consistency,
            "wall_seconds": float(wall),
            "long_turn_scan": False,
        }
        meta["identity_refinement"] = refinement
        meta["identity_consistency"] = consistency
        meta["identity_local_scan"] = {
            "enabled": False,
            "reason": "omitido_por_presupuesto_ultra_calidad",
            "scanned_turns": 0,
            "applied_changes": 0,
        }
        meta["identity_wall_seconds"] = float(wall)
        meta["detected_speakers_before_identity"] = before
        meta["detected_speakers"] = after
        log(
            "Ultra Calidad identidad ligera: "
            f"{before} → {after} cluster(s) · "
            f"{int(stats['calls'])} embedding(s) · {wall:.2f}s."
        )
        return refined, meta
