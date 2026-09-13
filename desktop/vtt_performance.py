#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Política de rendimiento V5.2.

Los perfiles globales coordinan modelo ASR, perfil ASR, activación/conteo de
hablantes y perfil de diarización. ``Personalizado`` conserva todos los
controles individuales.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional


GLOBAL_PROFILES: Dict[str, Dict[str, Any]] = {
    "Rápido": {
        "model": "small",
        "asr_profile": "Rapido",
        "diarize": True,
        "speaker_mode": "Auto",
        "diar_profile": "Rápida",
        "target_processing_ratio": 0.85,
        "description": "Prioriza velocidad en CPU con hablantes Auto.",
    },
    "Equilibrado": {
        "model": "small",
        "asr_profile": "Equilibrado",
        "diarize": True,
        "speaker_mode": "Auto",
        "diar_profile": "Equilibrada",
        "target_processing_ratio": 1.0,
        "description": "Recomendado: busca terminar cerca o bajo tiempo real.",
    },
    "Preciso": {
        "model": "medium",
        "asr_profile": "Preciso",
        "diarize": True,
        "speaker_mode": "Auto",
        # Precisa 0.10 queda disponible solo en Personalizado/avanzado: la
        # prueba institucional mostró un costo incompatible con uso habitual.
        "diar_profile": "Equilibrada",
        "target_processing_ratio": 1.5,
        "description": "Mayor precisión ASR; diarización equilibrada y mayor presupuesto.",
    },
    "Personalizado": {
        "model": None,
        "asr_profile": None,
        "diarize": None,
        "speaker_mode": None,
        "diar_profile": None,
        "target_processing_ratio": None,
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


def infer_global_profile(
    model: str,
    asr_profile: str,
    diar_profile: str,
    diarize: Optional[bool] = None,
    speaker_mode: Optional[str] = None,
) -> str:
    """Reconoce un preset solo si todos los controles conocidos coinciden.

    Las llamadas antiguas de tres argumentos se conservan para herramientas y
    pruebas V5.1: pueden reconocer el antiguo ``medium/Preciso/Precisa`` como
    Preciso. La UI V5.2 pasa además ``diarize`` y ``speaker_mode``; allí esa
    combinación histórica queda ``Personalizado`` y no se transforma en el
    nuevo Preciso (Equilibrada 0.20) de forma silenciosa.
    """
    if diarize is None and speaker_mode is None:
        if (str(model), str(asr_profile), str(diar_profile)) == (
            "medium", "Preciso", "Precisa"
        ):
            return "Preciso"

    for name, cfg in GLOBAL_PROFILES.items():
        if name == "Personalizado":
            continue
        if (
            str(model) != str(cfg.get("model"))
            or str(asr_profile) != str(cfg.get("asr_profile"))
            or str(diar_profile) != str(cfg.get("diar_profile"))
        ):
            continue
        if diarize is not None and bool(diarize) != bool(cfg.get("diarize")):
            continue
        if speaker_mode is not None and str(speaker_mode) != str(cfg.get("speaker_mode")):
            continue
        return name
    return "Personalizado"


def diarization_budget_seconds(
    *, audio_seconds: float, asr_seconds: float, profile_name: str,
    reserve_seconds: float = 5.0,
) -> Optional[float]:
    """Presupuesto wall para diarización dentro del objetivo del preset.

    El objetivo se refiere a ``processing_seconds`` (no a descarga/carga de
    modelo). ``Personalizado`` no impone presupuesto automático.
    """
    cfg = global_profile(profile_name)
    ratio = cfg.get("target_processing_ratio")
    if ratio is None:
        return None
    audio = max(0.0, float(audio_seconds or 0.0))
    asr = max(0.0, float(asr_seconds or 0.0))
    reserve = max(0.0, float(reserve_seconds or 0.0))
    return max(0.0, audio * float(ratio) - asr - reserve)


def performance_status(metrics: Mapping[str, Any]) -> Dict[str, Any]:
    audio = max(0.0, float(metrics.get("audio_seconds", 0.0) or 0.0))
    processing = max(0.0, float(metrics.get("processing_seconds", 0.0) or 0.0))
    end_to_end = max(0.0, float(metrics.get("end_to_end_seconds", 0.0) or 0.0))
    asr = max(0.0, float(metrics.get("asr_seconds", 0.0) or 0.0))
    diar = max(0.0, float(metrics.get("diarization_seconds", 0.0) or 0.0))
    if audio <= 0:
        return {"target": "unknown", "within_realtime": None}
    out = {
        "target": "processing_seconds <= audio_seconds",
        "within_realtime": processing <= audio,
        "processing_to_audio": processing / audio,
        "asr_share": asr / processing if processing else 0.0,
        "diarization_share": diar / processing if processing else 0.0,
        "seconds_over_realtime": max(0.0, processing - audio),
    }
    if end_to_end > 0:
        out.update({
            "end_to_end_seconds": end_to_end,
            "end_to_end_to_audio": end_to_end / audio,
            "end_to_end_within_realtime": end_to_end <= audio,
            "end_to_end_seconds_over_realtime": max(0.0, end_to_end - audio),
        })
    return out
