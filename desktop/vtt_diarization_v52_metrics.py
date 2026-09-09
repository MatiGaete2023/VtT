#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Corrección de contabilidad temporal para la diarización V5.2.

La selección identity-aware puede ejecutar una o dos evaluaciones ligeras antes
de la verificación final. El motor V5.2 original registraba correctamente esas
operaciones dentro del wall total de diarización, pero ``identity_wall_seconds``
solo sumaba la etapa final y, cuando existía, el precheck inicial. Esta capa
conserva la lógica acústica intacta y contabiliza todas las evaluaciones
ligeras ejecutadas mediante despacho dinámico de ``_light_identity``.
"""
from __future__ import annotations

from typing import Any, Dict

import vtt_diarization_v52 as base


def identity_wall_total(final_wall_seconds: float, light_wall_seconds: float) -> float:
    """Suma etapas de identidad sin duplicar precheck/selección."""
    return max(0.0, float(final_wall_seconds or 0.0)) + max(
        0.0, float(light_wall_seconds or 0.0)
    )


class DiarizationEngine(base.DiarizationEngine):
    """Mismo motor V5.2 con métricas de identidad completas."""

    def __init__(self, carpeta_modelos):
        super().__init__(carpeta_modelos)
        self._v52_light_identity_wall_seconds = 0.0

    def _light_identity(self, turnos, context, *, max_total=base.PRECHECK_MAX_EMBEDDINGS):
        result = super()._light_identity(
            turnos, context, max_total=max_total
        )
        if result is not None:
            self._v52_light_identity_wall_seconds += max(
                0.0, float(result.get("wall_seconds", 0.0) or 0.0)
            )
        return result

    def diarize(self, *args, **kwargs):
        self._v52_light_identity_wall_seconds = 0.0
        turnos, meta = super().diarize(*args, **kwargs)
        meta = dict(meta or {})
        verification: Dict[str, Any] = dict(meta.get("identity_verification") or {})
        if verification.get("enabled"):
            final_wall = float(verification.get("wall_seconds", 0.0) or 0.0)
            light_wall = float(self._v52_light_identity_wall_seconds)
            total = identity_wall_total(final_wall, light_wall)
            verification["final_stage_wall_seconds"] = final_wall
            verification["light_identity_wall_seconds"] = light_wall
            verification["total_wall_seconds"] = total
            meta["identity_verification"] = verification
            meta["identity_wall_seconds"] = total
        return turnos, meta
