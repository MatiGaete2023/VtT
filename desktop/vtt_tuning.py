#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ajustes conservadores derivados de pruebas reales de VtT.

Mantiene fuera de la UI la logica de normalizacion de hablantes para poder
probarla sin Tkinter ni modelos de audio.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Sequence, Tuple

# sherpa-onnx documenta que un umbral mayor produce menos clusters. Su ejemplo
# oficial para numero desconocido usa 0.90; el valor anterior de VtT (0.50)
# sobre-segmento una prueba real de 7:18.
AUTO_CLUSTER_THRESHOLD = 0.90


def renumerar_hablantes_en_uso(
    segmentos: Sequence[Mapping[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Renombra solo hablantes realmente asignados, por primera aparicion.

    Los IDs de clustering pueden ser dispersos (p.ej. 1, 3, 9, 14). La salida
    visible siempre queda Persona 1, Persona 2... sin saltos. Se conserva el ID
    original en ``speaker_raw_id`` para trazabilidad.
    """
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
