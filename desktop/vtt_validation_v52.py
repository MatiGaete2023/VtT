#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validación V5.2: distingue clusters acústicos, identidad y texto."""
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Sequence

import vtt_validation as structural
import vtt_validation_v51 as v51


def evaluar(
    diar_meta: Mapping[str, Any], *, acoustic_clusters: int,
    identity_clusters: int, text_speakers: int,
    unassigned_raw_ids: Optional[Sequence[int]] = None,
    manual_requested: Optional[int] = None,
) -> Dict[str, Any]:
    out = structural.evaluar_conteo_hablantes(
        diar_meta, int(identity_clusters), manual_requested=manual_requested
    )
    out = v51.aplicar_consistencia_identidad(
        out, diar_meta.get("identity_consistency") or {}
    )
    out.update({
        "raw_acoustic_clusters": int(acoustic_clusters),
        "identity_clusters_after_refinement": int(identity_clusters),
        "text_assigned_speakers": int(text_speakers),
        "unassigned_acoustic_clusters": len(list(unassigned_raw_ids or [])),
        "unassigned_raw_ids": [int(x) for x in (unassigned_raw_ids or [])],
    })
    if manual_requested is None and out.get("status") in {
        "estimacion_sospechosa", "estimacion_inestable",
        "estimacion_sospechosa_identidad", "estimacion_con_reservas_identidad",
    }:
        out["ambiguous"] = True
    else:
        out["ambiguous"] = False
    return out


def etiqueta(validacion: Mapping[str, Any]) -> str:
    if validacion.get("ambiguous"):
        return "resultado ambiguo; revisar hablantes"
    return v51.etiqueta_confianza(validacion)
