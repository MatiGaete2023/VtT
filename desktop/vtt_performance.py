#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Política de rendimiento V5.2.

Los perfiles globales coordinan modelo ASR, perfil ASR y diarización. Los
controles individuales siguen disponibles mediante ``Personalizado``.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping


GLOBAL_PROFILES: Dict[str, Dict[str, Any]] = {
    "Rápido": {
        "model": "small",
        "asr_profile": "Rapido",
        "diar_profile": "Rápida",
        "description": "Prioriza velocidad en CPU.",
    },
    "Equilibrado": {
        "model": "small",
        "asr_profile": "Equilibrado",
        "diar_profile": "Equilibrada",
        "description": "Recomendado: busca terminar cerca o bajo tiempo real.",
    },
    "Preciso": {
        "model": "medium",
        "asr_profile": "Preciso",
        "diar_profile": "Precisa",
        "description": "Mayor costo; úsalo cuando la precisión justifique la demora.",
    },
    "Personalizado": {
        "model": None,
        "asr_profile": None,
        "diar_profile": None,
        "description": "Conserva los controles individuales.",
    },
}

ASR_BENCHMARK_MATRIX = (
    ("medium", "Preciso"),
    ("medium", "Equilibrado"),
    ("small", "Preciso"),
    ("small", "Equilibrado"),
)


def global_profile(name: str) -> Dict[str, Any]:
    key = str(name or "Equilibrado")
    if key not in GLOBAL_PROFILES:
        key = "Equilibrado"
    out = dict(GLOBAL_PROFILES[key]); out["name"] = key
    return out


def performance_status(metrics: Mapping[str, Any]) -> Dict[str, Any]:
    audio = max(0.0, float(metrics.get("audio_seconds", 0.0) or 0.0))
    processing = max(0.0, float(metrics.get("processing_seconds", 0.0) or 0.0))
    asr = max(0.0, float(metrics.get("asr_seconds", 0.0) or 0.0))
    diar = max(0.0, float(metrics.get("diarization_seconds", 0.0) or 0.0))
    if audio <= 0:
        return {"target": "unknown", "within_realtime": None}
    return {
        "target": "processing_seconds <= audio_seconds",
        "within_realtime": processing <= audio,
        "processing_to_audio": processing / audio,
        "asr_share": asr / processing if processing else 0.0,
        "diarization_share": diar / processing if processing else 0.0,
        "seconds_over_realtime": max(0.0, processing - audio),
    }
