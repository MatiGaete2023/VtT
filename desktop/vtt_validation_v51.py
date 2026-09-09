#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validación V5.1: incorpora consistencia acústica de identidad."""
from __future__ import annotations
from typing import Any, Dict, Mapping


def aplicar_consistencia_identidad(validacion: Mapping[str, Any], consistencia: Mapping[str, Any]) -> Dict[str, Any]:
    out = dict(validacion or {})
    overall = str(consistencia.get("overall_confidence", "sin_datos") or "sin_datos")
    out["identity_confidence"] = overall
    out["identity_low_confidence_speakers"] = int(consistencia.get("low_confidence_speakers", 0) or 0)
    out["identity_insufficient_speakers"] = int(consistencia.get("insufficient_speakers", 0) or 0)
    if out.get("status") == "conteo_fijado_por_usuario":
        return out
    if overall == "baja":
        out["status"] = "estimacion_sospechosa_identidad"
    elif overall in {"media", "sin_datos"} and out.get("status") in {
        "estimacion_acustica_estable", "estimacion_estable_tras_reintento"
    }:
        out["status"] = "estimacion_con_reservas_identidad"
    return out


def etiqueta_confianza(validacion: Mapping[str, Any]) -> str:
    status = str(validacion.get("status", "") or "")
    if status in {"estimacion_sospechosa", "estimacion_inestable", "estimacion_sospechosa_identidad"}:
        return "baja confianza"
    if status in {"estimacion_con_reservas_identidad", "estimacion_estable_tras_reintento"}:
        return "confianza media"
    if status == "estimacion_acustica_estable":
        return "confianza estructural alta"
    if status == "conteo_fijado_por_usuario":
        return "conteo fijado por usuario"
    return "confianza no determinada"
