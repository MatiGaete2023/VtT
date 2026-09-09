#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reportes V5.2: conteos separados, identidad interpretable y rendimiento."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

from docx import Document

import vtt_performance as perf
import vtt_reporting_v51 as v51
import vtt_validation_v52 as validation52


def documento_json_detallado(
    archivo: str, modelo: str, idioma: str, texto: str,
    segmentos: Sequence[Mapping[str, Any]], bloques: Sequence[Mapping[str, Any]],
    speakers: Sequence[Mapping[str, Any]], metricas: Mapping[str, Any],
    perfil: str, glosario: str,
) -> Dict[str, Any]:
    doc = v51.documento_json_detallado(
        archivo, modelo, idioma, texto, segmentos, bloques,
        speakers, metricas, perfil, glosario,
    )
    doc["schema_version"] = max(7, int(doc.get("schema_version", 0) or 0))
    diar = doc.setdefault("diarization", {})
    diar["speaker_counts"] = metricas.get("speaker_counts") or {}
    diar["auto_precheck"] = metricas.get("auto_precheck") or {}
    diar["identity_aware_selection"] = metricas.get("identity_aware_selection") or {}
    diar["retry_requested"] = bool(metricas.get("auto_retry_requested", False))
    diar["retry_avoided"] = bool(metricas.get("auto_retry_avoided", False))
    doc["performance"] = metricas.get("performance") or perf.performance_status(metricas)
    doc["global_profile"] = metricas.get("global_profile")
    return doc


def _find_row(table, label: str):
    for row in table.rows:
        if row.cells and row.cells[0].text.strip() == label:
            return row
    return None


def _fmt_identity(sp: Mapping[str, Any]) -> str:
    confidence = str(sp.get("confidence", "sin_datos"))
    turns = int(sp.get("turns", 0) or 0)
    embedded = int(sp.get("embedded_turns", 0) or 0)
    seconds = float(sp.get("total_seconds", 0.0) or 0.0)
    gap = float(sp.get("max_gap_seconds", 0.0) or 0.0)
    base = f"{confidence} · {turns} turno(s) · {seconds:.1f} s · {embedded} muestra(s) acústica(s)"
    if embedded == 0:
        return base + " · similitud no evaluable"
    if embedded == 1:
        return base + " · muestra única; similitud no evaluable"
    if embedded == 2:
        pair = sp.get("pair_similarity"); rival = sp.get("rival_similarity_max")
        if pair is not None:
            base += f" · similitud entre apariciones {float(pair):.2f}"
        if rival is not None:
            base += f" · rival máx {float(rival):.2f}"
        if gap > 0:
            base += f" · separación máx {gap:.1f} s"
        return base
    med = sp.get("prototype_similarity_median"); minv = sp.get("prototype_similarity_min")
    rival = sp.get("rival_similarity_max")
    if med is not None:
        base += f" · prototipo mediana {float(med):.2f}"
    if minv is not None:
        base += f" · mínimo {float(minv):.2f}"
    if rival is not None:
        base += f" · rival máx {float(rival):.2f}"
    return base


def escribir_docx_detallado(
    ruta: Path, archivo: str, modelo: str, idioma: str,
    bloques: Sequence[Mapping[str, Any]], metricas: Mapping[str, Any], perfil: str,
) -> None:
    v51.escribir_docx_detallado(ruta, archivo, modelo, idioma, bloques, metricas, perfil)
    doc = Document(str(ruta))
    if not doc.tables:
        doc.save(str(ruta)); return
    table = doc.tables[0]
    counts = metricas.get("speaker_counts") or {}
    valid = metricas.get("speaker_count_validation") or {}
    acoustic = int(counts.get("raw_acoustic_clusters", metricas.get("speaker_detected", 0)) or 0)
    identity_n = int(counts.get("identity_clusters_after_refinement", acoustic) or 0)
    text_n = int(counts.get("text_assigned_speakers", metricas.get("speaker_text_assigned", 0)) or 0)

    row = _find_row(table, "Hablantes")
    if row is not None and metricas.get("speaker_mode") == "Auto":
        label = validation52.etiqueta(valid)
        row.cells[1].text = f"Auto · estimación acústica: {identity_n} · con texto: {text_n} · {label}"
    rowv = _find_row(table, "Validación conteo hablantes")
    if rowv is not None:
        rowv.cells[1].text = (
            f"{valid.get('status', '—')} · acústicos {identity_n} · con texto {text_n} · "
            f"ground truth {'sí' if valid.get('ground_truth_available') else 'no'} · "
            f"identidad {valid.get('identity_confidence', 'sin_datos')}"
        )

    consistency = metricas.get("identity_consistency") or {}
    unassigned = set(int(x) for x in (counts.get("unassigned_raw_ids") or []))
    for sp in consistency.get("speakers", []) or []:
        raw = int(sp.get("speaker", -1))
        display = sp.get("display_name")
        old_label = f"Identidad {display}" if display else f"Identidad ID raw {raw}"
        r = _find_row(table, old_label)
        if r is not None:
            if display:
                r.cells[0].text = f"Identidad {display}"
            elif raw in unassigned:
                r.cells[0].text = f"Cluster acústico raw {raw} (sin texto)"
            else:
                r.cells[0].text = f"Cluster acústico raw {raw}"
            r.cells[1].text = _fmt_identity(sp)

    perf_status = metricas.get("performance") or perf.performance_status(metricas)
    rows = [
        ("Clusters sherpa seleccionados", str(acoustic)),
        ("Clusters tras control identidad", str(identity_n)),
        ("Hablantes con texto", str(text_n)),
        ("Clusters acústicos sin texto", ", ".join(str(x) for x in sorted(unassigned)) if unassigned else "0"),
        ("Segunda pasada solicitada", "Sí" if metricas.get("auto_retry_requested") else "No"),
        ("Segunda pasada evitada", "Sí" if metricas.get("auto_retry_avoided") else "No"),
    ]
    pre = metricas.get("auto_precheck") or {}
    if pre.get("enabled"):
        rows.append((
            "Precheck rendimiento Auto",
            f"{float(pre.get('wall_seconds', 0.0) or 0.0):.2f} s · "
            f"{int(pre.get('speakers_before', 0) or 0)}→{int(pre.get('speakers_after', 0) or 0)} · "
            f"{'aceptado' if pre.get('accepted') else 'no concluyente'}",
        ))
    sel = metricas.get("identity_aware_selection") or {}
    if sel.get("enabled"):
        rows.append((
            "Selección Auto identity-aware",
            f"{sel.get('selected_candidate', '—')} · score 1 {float(sel.get('first_score', 0.0)):.2f} · "
            f"score 2 {float(sel.get('second_score', 0.0)):.2f}",
        ))
    if perf_status.get("within_realtime") is not None:
        rows.append((
            "Presupuesto de rendimiento",
            ("cumplido" if perf_status.get("within_realtime") else "sobre tiempo real")
            + f" · proceso/audio {float(perf_status.get('processing_to_audio', 0.0)):.2f}×",
        ))
    if metricas.get("global_profile"):
        rows.append(("Modo global", str(metricas.get("global_profile"))))
    for k, v in rows:
        if _find_row(table, k) is None:
            cells = table.add_row().cells; cells[0].text = k; cells[1].text = str(v)
    doc.save(str(ruta))
