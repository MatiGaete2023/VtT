#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Alineación palabra↔hablante y división de segmentos por cambios de voz."""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple


def _ov(a0: float, a1: float, b0: float, b1: float) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))


def _turnos_validos(turnos: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for t in turnos:
        try:
            a, b = float(t.get("start", 0.0)), float(t.get("end", 0.0))
            sp = int(t.get("speaker", 0))
        except (TypeError, ValueError):
            continue
        if b > a:
            out.append({"start": a, "end": b, "speaker": sp})
    return sorted(out, key=lambda x: (x["start"], x["end"]))


def _speaker_intervalo(a: float, b: float, turnos: Sequence[Mapping[str, Any]],
                       max_nearest_gap: float = 0.65) -> Optional[int]:
    por: Dict[int, float] = {}
    for t in turnos:
        ov = _ov(a, b, float(t["start"]), float(t["end"]))
        if ov > 0:
            sp = int(t["speaker"])
            por[sp] = por.get(sp, 0.0) + ov
    if por:
        return max(por, key=por.get)

    medio = (a + b) / 2.0
    mejor = None
    distancia = float("inf")
    for t in turnos:
        if float(t["start"]) <= medio <= float(t["end"]):
            return int(t["speaker"])
        d = min(abs(medio - float(t["start"])), abs(medio - float(t["end"])))
        if d < distancia:
            distancia, mejor = d, int(t["speaker"])
    return mejor if distancia <= max_nearest_gap else None


def _dur_palabras(words: Sequence[Mapping[str, Any]], i0: int, i1: int) -> float:
    vals = [w for w in words[i0:i1] if w.get("start") is not None and w.get("end") is not None]
    if not vals:
        return 0.0
    return max(0.0, float(vals[-1]["end"]) - float(vals[0]["start"]))


def _suavizar_etiquetas(labels: List[Optional[int]], words: Sequence[Mapping[str, Any]],
                         min_run_words: int = 2, min_run_seconds: float = 0.35) -> List[Optional[int]]:
    """Elimina flips interiores muy breves cuando ambos lados coinciden."""
    out = list(labels)
    if len(out) < 3:
        return out
    changed = True
    while changed:
        changed = False
        runs = []
        i = 0
        while i < len(out):
            j = i + 1
            while j < len(out) and out[j] == out[i]:
                j += 1
            runs.append((i, j, out[i]))
            i = j
        for r in range(1, len(runs) - 1):
            a0, a1, sp = runs[r]
            prev_sp = runs[r - 1][2]
            next_sp = runs[r + 1][2]
            if prev_sp is None or prev_sp != next_sp or sp == prev_sp:
                continue
            breve = (a1 - a0) < min_run_words or _dur_palabras(words, a0, a1) < min_run_seconds
            if breve:
                for k in range(a0, a1):
                    out[k] = prev_sp
                changed = True
                break
    return out


def _texto_words(words: Sequence[Mapping[str, Any]]) -> str:
    piezas = [str(w.get("word", w.get("text", "")) or "") for w in words]
    unido = "".join(piezas).strip()
    if len(piezas) > 1 and " " not in unido:
        unido = " ".join(x.strip() for x in piezas)
    return " ".join(unido.split())


def alinear_y_dividir(
    segmentos: Sequence[Mapping[str, Any]],
    turnos: Sequence[Mapping[str, Any]],
    *,
    min_run_words: int = 2,
    min_run_seconds: float = 0.35,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Asigna hablante por palabra y divide el segmento si la voz cambia."""
    tv = _turnos_validos(turnos)
    salida: List[Dict[str, Any]] = []
    total_words = assigned_words = fallback = split_sources = internal_switches = 0

    for src_idx, original in enumerate(segmentos):
        seg = dict(original)
        words = [dict(w) for w in (seg.get("words") or [])
                 if w.get("start") is not None and w.get("end") is not None]
        total_words += len(words)

        if not words:
            sp = _speaker_intervalo(
                float(seg.get("start", 0.0)), float(seg.get("end", 0.0)), tv
            )
            seg["speaker_id"] = sp
            seg["speaker"] = f"Persona {sp + 1}" if sp is not None else None
            seg["source_segment_id"] = seg.get("id", src_idx)
            salida.append(seg)
            fallback += 1
            continue

        labels = []
        for w in words:
            sp = _speaker_intervalo(float(w["start"]), float(w["end"]), tv)
            labels.append(sp)
            if sp is not None:
                assigned_words += 1
        labels = _suavizar_etiquetas(
            labels, words, min_run_words=min_run_words, min_run_seconds=min_run_seconds
        )

        for i, sp in enumerate(labels):
            if sp is not None:
                continue
            prev_sp = next((labels[k] for k in range(i - 1, -1, -1) if labels[k] is not None), None)
            next_sp = next((labels[k] for k in range(i + 1, len(labels)) if labels[k] is not None), None)
            labels[i] = prev_sp if prev_sp == next_sp else (prev_sp if next_sp is None else next_sp)

        groups = []
        i = 0
        while i < len(words):
            j = i + 1
            while j < len(words) and labels[j] == labels[i]:
                j += 1
            groups.append((i, j, labels[i]))
            i = j

        if len(groups) > 1:
            split_sources += 1
            internal_switches += len(groups) - 1

        for g0, g1, sp in groups:
            ws = words[g0:g1]
            sub = {
                k: v for k, v in seg.items()
                if k not in {"start", "end", "text", "words", "speaker", "speaker_id", "id"}
            }
            sub.update({
                "id": len(salida),
                "source_segment_id": seg.get("id", src_idx),
                "start": float(ws[0]["start"]),
                "end": float(ws[-1]["end"]),
                "text": _texto_words(ws),
                "words": ws,
                "speaker_id": sp,
                "speaker": f"Persona {sp + 1}" if sp is not None else None,
            })
            salida.append(sub)

    for i, seg in enumerate(salida):
        seg["id"] = i

    meta = {
        "mode": "word_level" if total_words else "segment_fallback",
        "input_segments": len(segmentos),
        "output_segments": len(salida),
        "word_count": total_words,
        "assigned_words": assigned_words,
        "unassigned_words": max(0, total_words - assigned_words),
        "fallback_segments": fallback,
        "split_source_segments": split_sources,
        "speaker_switches_inside_segments": internal_switches,
    }
    return salida, meta
