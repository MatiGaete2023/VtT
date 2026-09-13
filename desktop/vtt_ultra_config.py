#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Configuración de las variantes VtT Ultra para Windows.

La rama mantiene dos objetivos deliberadamente distintos:
- ``Ultrarrápido``: máximo ahorro de tiempo, alineación por segmento;
- ``Ultra Calidad 90s``: usa parte del margen ganado para mejorar texto y
  separación de voces, manteniendo una sola pasada sherpa.
"""
from __future__ import annotations

import vtt_diarization_v4 as diar4
import vtt_performance as perf

ULTRA_PROFILE_NAME = "Ultrarrápido"
ULTRA_QUALITY_PROFILE_NAME = "Ultra Calidad 90s"
ULTRA_DIAR_PROFILE = "Ultrarrápida"
ULTRA_WINDOW_SHIFT_RATIO = 0.35
ULTRA_AUTO_THRESHOLD = 0.82
ULTRA_TARGET_PROCESSING_RATIO = 0.60
# 0.22 * 404 s ~= 88.9 s para el video patrón de 6:44.
ULTRA_QUALITY_TARGET_PROCESSING_RATIO = 0.22
ULTRA_IDENTITY_MAX_EMBEDDINGS = 10
ULTRA_IDENTITY_MAX_PER_SPEAKER = 2


def install_ultra_mode() -> None:
    """Instala los presets y el perfil de diarización exclusivos de esta rama."""
    diar4.DIARIZATION_PROFILES[ULTRA_DIAR_PROFILE] = {
        "window_shift_ratio": ULTRA_WINDOW_SHIFT_RATIO,
        "description": (
            "Máximo ahorro de ventanas; menor resolución temporal que Rápida."
        ),
    }
    perf.GLOBAL_PROFILES[ULTRA_PROFILE_NAME] = {
        "model": "tiny",
        "asr_profile": "Rapido",
        "diarize": True,
        "speaker_mode": "Auto",
        "diar_profile": ULTRA_DIAR_PROFILE,
        "target_processing_ratio": ULTRA_TARGET_PROCESSING_RATIO,
        "description": (
            "Windows ultrarrápido: tiny + beam 1 + una pasada sherpa + "
            "alineación por segmento."
        ),
    }
    perf.GLOBAL_PROFILES[ULTRA_QUALITY_PROFILE_NAME] = {
        "model": "base",
        "asr_profile": "Rapido",
        "diarize": True,
        "speaker_mode": "Auto",
        "diar_profile": ULTRA_DIAR_PROFILE,
        "target_processing_ratio": ULTRA_QUALITY_TARGET_PROCESSING_RATIO,
        "description": (
            "Usa el margen de Ultra para base + timestamps por palabra + "
            "alineación fina + identidad ligera, sin segunda pasada sherpa."
        ),
    }


def is_ultra_quality(profile_name: str) -> bool:
    return str(profile_name or "") == ULTRA_QUALITY_PROFILE_NAME


def ultra_threshold_for_speaker_mode(mode: str) -> float:
    """Auto usa un único threshold orientado a fusionar microclusters."""
    return ULTRA_AUTO_THRESHOLD if str(mode) == "Auto" else 0.5


def ultra_word_timestamps(user_requested: bool, profile_name: str = ULTRA_PROFILE_NAME) -> bool:
    """Calidad 90s fuerza palabras; Ultra máxima solo respeta petición manual."""
    if is_ultra_quality(profile_name):
        return True
    return bool(user_requested)


def ultra_tradeoffs(profile_name: str = ULTRA_PROFILE_NAME) -> list[str]:
    if is_ultra_quality(profile_name):
        return [
            "una_sola_pasada_sherpa",
            "identidad_ligera_acotada",
            "alineacion_hablante_por_palabra",
            "timestamps_palabra_forzados",
            "window_shift_0_35",
            "sin_reasr_selectivo_hasta_benchmark_real",
        ]
    return [
        "una_sola_pasada_sherpa",
        "sin_verificacion_identidad_v52",
        "alineacion_hablante_por_segmento",
        "timestamps_palabra_no_forzados",
        "window_shift_0_35",
    ]
