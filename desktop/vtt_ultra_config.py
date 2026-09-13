#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Configuración de la variante VtT Ultra para Windows.

Esta rama prioriza velocidad por sobre refinamiento acústico. Mantiene
transcripción local, timestamps por segmento y una sola pasada sherpa para
intentar separar hablantes.
"""
from __future__ import annotations

import vtt_diarization_v4 as diar4
import vtt_performance as perf

ULTRA_PROFILE_NAME = "Ultrarrápido"
ULTRA_DIAR_PROFILE = "Ultrarrápida"
ULTRA_WINDOW_SHIFT_RATIO = 0.35
ULTRA_AUTO_THRESHOLD = 0.82
ULTRA_TARGET_PROCESSING_RATIO = 0.60


def install_ultra_mode() -> None:
    """Instala el preset y perfil de diarización de esta rama.

    Se hace en runtime para no modificar la semántica de V5.2.1 estable.
    """
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


def ultra_threshold_for_speaker_mode(mode: str) -> float:
    """Auto usa un único threshold orientado a fusionar microclusters."""
    return ULTRA_AUTO_THRESHOLD if str(mode) == "Auto" else 0.5


def ultra_word_timestamps(user_requested: bool) -> bool:
    """No fuerza timestamps por palabra solo por activar diarización."""
    return bool(user_requested)


def ultra_tradeoffs() -> list[str]:
    return [
        "una_sola_pasada_sherpa",
        "sin_verificacion_identidad_v52",
        "alineacion_hablante_por_segmento",
        "timestamps_palabra_no_forzados",
        "window_shift_0_35",
    ]
