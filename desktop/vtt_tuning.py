#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ajustes derivados de pruebas reales de VtT.

Contiene lógica pura para:
- normalizar hablantes visibles;
- ajustar Auto sin repetir trabajo salvo conteos extremos;
- derivar regiones de voz seguras desde los segmentos ASR.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Sequence, Tuple

AUTO_BALANCED_THRESHOLD = 0.74
AUTO_SPLIT_THRESHOLD = 0.66
AUTO_MERGE_THRESHOLD = 0.84
AUTO_MAX_SPEAKERS = 8


def ajuste_auto_por_conteo(conteo: int) -> float | None:
    """Devuelve un umbral de corrección solo para resultados extremos."""
    n = max(0, int(conteo))
    if n <= 1:
        return AUTO_SPLIT_THRESHOLD
    if n > AUTO_MAX_SPEAKERS:
        return AUTO_MERGE_THRESHOLD
    return None


def renumerar_hablantes_en_uso(
    segmentos: Sequence[Mapping[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Renombra solo hablantes asignados, por orden de primera aparición."""
    salida = [dict(s) for s in segmentos]
    orden_raw: List[int] = []

    for seg in sorted(salida, key=lambda x: float(x.get("start", 0.0) or 0.0)):
        raw = seg.get("speaker_id")
        if raw is None:
            continue
        raw = int(raw)
        if raw not in orden_raw:
            orden_raw.append(raw)

    mapa = {raw: i + 1 for i, raw in enumerate(orden_raw)}
    for seg in salida:
        raw = seg.get("speaker_id")
        if raw is None:
            seg["speaker"] = None
            continue
        raw = int(raw)
        numero = mapa[raw]
        seg["speaker_raw_id"] = raw
        seg["speaker_id"] = numero - 1
        seg["speaker"] = f"Persona {numero}"

    speakers = [
        {
            "id": f"speaker_{numero - 1:02d}",
            "numeric_id": numero - 1,
            "raw_numeric_id": raw,
            "display_name": f"Persona {numero}",
        }
        for raw, numero in mapa.items()
    ]
    return salida, speakers


def regiones_voz_desde_segmentos(
    segmentos: Sequence[Mapping[str, Any]],
    duracion_audio: float,
    padding: float = 0.35,
    unir_gap: float = 0.60,
    max_coverage: float = 0.88,
    min_speech_seconds: float = 8.0,
) -> Tuple[List[Tuple[float, float]], Dict[str, Any]]:
    """Obtiene regiones de voz a partir de ASR para acelerar diarización.

    Solo activa la reducción si ahorra al menos ~12 % del audio, existen al
    menos dos regiones y hay suficiente habla. Si no se cumplen esas condiciones
    devuelve una lista vacía: el llamador debe diarizar el audio completo.
    """
    dur = max(0.0, float(duracion_audio or 0.0))
    if dur <= 0:
        return [], {"enabled": False, "reason": "duracion_desconocida"}

    regiones: List[Tuple[float, float]] = []
    pad = max(0.0, float(padding))
    for seg in segmentos:
        try:
            ini = max(0.0, float(seg.get("start", 0.0)) - pad)
            fin = min(dur, float(seg.get("end", 0.0)) + pad)
        except (TypeError, ValueError):
            continue
        if fin <= ini or not str(seg.get("text", "")).strip():
            continue
        regiones.append((ini, fin))

    if not regiones:
        return [], {"enabled": False, "reason": "sin_regiones"}

    regiones.sort()
    fusionadas: List[List[float]] = []
    gap = max(0.0, float(unir_gap))
    for ini, fin in regiones:
        if not fusionadas or ini - fusionadas[-1][1] > gap:
            fusionadas.append([ini, fin])
        else:
            fusionadas[-1][1] = max(fusionadas[-1][1], fin)

    total_voz = sum(fin - ini for ini, fin in fusionadas)
    coverage = total_voz / dur if dur else 1.0
    meta = {
        "enabled": False,
        "regions": len(fusionadas),
        "audio_seconds": dur,
        "speech_seconds": total_voz,
        "coverage": coverage,
        "saved_seconds": max(0.0, dur - total_voz),
    }

    if len(fusionadas) < 2:
        meta["reason"] = "una_sola_region"
        return [], meta
    if total_voz < float(min_speech_seconds):
        meta["reason"] = "muy_poca_voz"
        return [], meta
    if coverage >= float(max_coverage):
        meta["reason"] = "ahorro_insuficiente"
        return [], meta

    meta["enabled"] = True
    meta["reason"] = "ok"
    return [(float(a), float(b)) for a, b in fusionadas], meta
