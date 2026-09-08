#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Evaluación explícita del conteo de hablantes sin confundir estimación con ground truth."""
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional


def evaluar_conteo_hablantes(
    diar_meta: Mapping[str, Any],
    detected_speakers: int,
    *,
    manual_requested: Optional[int] = None,
) -> Dict[str, Any]:
    analysis = dict(diar_meta.get("selected_analysis") or {})
    penalty = float(analysis.get("penalty", 0.0) or 0.0)
    retry = bool(diar_meta.get("retry", False))
    delta = diar_meta.get("stability_delta_speakers")
    try:
        delta_i = int(delta) if delta is not None else 0
    except (TypeError, ValueError):
        delta_i = 0

    if manual_requested is not None:
        status = "conteo_fijado_por_usuario"
    elif detected_speakers <= 0:
        status = "sin_estimacion"
    elif retry and delta_i > 3:
        status = "estimacion_inestable"
    elif penalty >= 2.0:
        status = "estimacion_sospechosa"
    elif retry:
        status = "estimacion_estable_tras_reintento"
    else:
        status = "estimacion_acustica_estable"

    return {
        "status": status,
        "estimated_speakers": int(detected_speakers or 0),
        "manual_requested": manual_requested,
        "structural_penalty": penalty,
        "auto_retry": retry,
        "stability_delta_speakers": delta_i,
        "ground_truth_available": False,
        "ground_truth_speakers": None,
    }
