#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Identidad V5.2: decisiones rival-aware y escaneo largo por sonda barata.

Se apoya en las primitivas V5.1, pero cambia dos decisiones:
1) una identidad de dos turnos puede ser sospechosa aunque su pair_similarity
   no caiga bajo 0.35 si otra identidad rival explica mucho mejor uno de ellos;
2) un turno largo se prueba primero con 3 ventanas. Solo si esa sonda resulta
   heterogénea se paga el escaneo detallado de hasta 6 ventanas.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

import vtt_identity as base

Embedding = base.Embedding
EmbedInterval = base.EmbedInterval
normalizar = base.normalizar
similitud = base.similitud
extraer_embeddings_turnos = base.extraer_embeddings_turnos
construir_prototipos = base.construir_prototipos
MIN_EMBED_SECONDS = base.MIN_EMBED_SECONDS
LOCAL_SCAN_MIN_SECONDS = base.LOCAL_SCAN_MIN_SECONDS

PAIR_SOFT_THRESHOLD = 0.50
RIVAL_STRONG_THRESHOLD = 0.58
RIVAL_PAIR_MARGIN = 0.15
RIVAL_SECOND_MARGIN = 0.10

PROBE_WINDOWS = 3
PROBE_MUTUAL_HOMOGENEITY = 0.62
PROBE_CURRENT_HOMOGENEITY = 0.58


def _dur(t: Mapping[str, Any]) -> float:
    return base._dur(t)


def _sp(t: Mapping[str, Any]) -> int:
    return base._sp(t)


def _grupos(turnos, embeddings):
    return base._grupos(turnos, embeddings)


def _recount(meta: Dict[str, Any], turnos) -> Dict[str, Any]:
    out = dict(meta or {})
    out["speakers_after"] = len({_sp(t) for t in turnos})
    out["reassigned_turns"] = len(out.get("reassignments") or [])
    out["new_identities"] = len({
        int(x.get("to")) for x in (out.get("reassignments") or [])
        if x.get("reason") == "new_identity_from_inconsistent_turn"
    })
    return out


def refinar_turnos(turnos, embeddings, *, allow_new_identities: bool = True):
    """V5.1 + control de dos apariciones frente a identidades rivales."""
    out, meta = base.refinar_turnos(
        turnos, embeddings, allow_new_identities=allow_new_identities
    )
    reassignments = list(meta.get("reassignments") or [])
    protos = construir_prototipos(out, embeddings)
    grupos = _grupos(out, embeddings)

    for sp, idxs in list(grupos.items()):
        if len(idxs) != 2:
            continue
        pair = base._pair_similarity(idxs, embeddings)
        if pair is None or pair >= PAIR_SOFT_THRESHOLD:
            continue
        anchor, suspect = base._anchor_two(out, idxs)
        best_sp, best, second = base._best_other(embeddings[suspect], sp, protos)
        rival_conflict = (
            best_sp is not None
            and best >= RIVAL_STRONG_THRESHOLD
            and best - float(pair) >= RIVAL_PAIR_MARGIN
            and best - second >= RIVAL_SECOND_MARGIN
        )
        if rival_conflict:
            old = _sp(out[suspect])
            out[suspect]["speaker"] = int(best_sp)
            reassignments.append({
                "turn_index": int(suspect), "from": int(old), "to": int(best_sp),
                "reason": "two_turn_rival_explains_better",
                "pair_similarity": float(pair), "rival_similarity": float(best),
                "rival_margin_over_pair": float(best - pair),
                "anchor_turn_index": int(anchor),
            })

    meta = dict(meta or {})
    meta["reassignments"] = reassignments
    return out, _recount(meta, out)


def resumir_identidades(turnos, embeddings) -> Dict[str, Any]:
    """Resumen V5.2 que evita sobrevalorar prototipos de 1–2 muestras."""
    raw = base.resumir_identidades(turnos, embeddings)
    speakers = []
    low = medium = high = insufficient = 0
    for item in raw.get("speakers", []) or []:
        x = dict(item)
        n = int(x.get("embedded_turns", 0) or 0)
        pair = x.get("pair_similarity")
        rival = x.get("rival_similarity_max")
        if n == 0:
            label = "sin_datos"; insufficient += 1
        elif n == 1:
            label = "insuficiente"; insufficient += 1
        elif n == 2:
            p = float(pair) if pair is not None else -1.0
            r = float(rival) if rival is not None else -1.0
            if r >= RIVAL_STRONG_THRESHOLD and r - p >= RIVAL_PAIR_MARGIN:
                label = "baja"; low += 1
                x["identity_warning"] = "rival_mas_probable_que_identidad_actual"
            elif p >= 0.55:
                label = "alta"; high += 1
            elif p >= 0.40:
                label = "media"; medium += 1
            else:
                label = "baja"; low += 1
        else:
            med = x.get("prototype_similarity_median")
            min_own = x.get("prototype_similarity_min")
            r = x.get("rival_similarity_max")
            medf = float(med) if med is not None else 0.0
            minf = float(min_own) if min_own is not None else 0.0
            rf = float(r) if r is not None else -1.0
            if rf >= 0.62 and rf - minf >= 0.15:
                label = "media"; medium += 1
                x["identity_warning"] = "alguna_muestra_cercana_a_identidad_rival"
            elif medf >= 0.78:
                label = "alta"; high += 1
            elif medf >= 0.65:
                label = "media"; medium += 1
            else:
                label = "baja"; low += 1
        x["confidence"] = label
        speakers.append(x)
    overall = "baja" if low else (
        "media" if medium or insufficient else ("alta" if speakers else "sin_datos")
    )
    return {
        "overall_confidence": overall,
        "low_confidence_speakers": low,
        "medium_confidence_speakers": medium,
        "high_confidence_speakers": high,
        "insufficient_speakers": insufficient,
        "speakers": speakers,
    }


def identity_penalty(consistency: Mapping[str, Any]) -> float:
    """Penalización pequeña: complementa estructura, no reemplaza sherpa."""
    low = int(consistency.get("low_confidence_speakers", 0) or 0)
    medium = int(consistency.get("medium_confidence_speakers", 0) or 0)
    insuff = int(consistency.get("insufficient_speakers", 0) or 0)
    score = low * 1.50 + medium * 0.35 + min(insuff, 4) * 0.12
    for sp in consistency.get("speakers", []) or []:
        if sp.get("identity_warning"):
            score += 0.75
    return float(score)


def _probe_intervals(start: float, end: float):
    return base._window_intervals(start, end, base.LOCAL_WINDOW_SECONDS, PROBE_WINDOWS)


def _probe_homogeneous(turn, protos, embed_interval: EmbedInterval):
    start, end = float(turn.get("start", 0.0)), float(turn.get("end", 0.0))
    intervals = _probe_intervals(start, end)
    vals = [normalizar(embed_interval(a, b)) for a, b in intervals]
    vals = [v for v in vals if v is not None]
    if len(vals) < 2:
        return False, {"windows": len(vals), "reason": "datos_insuficientes"}
    current = protos.get(_sp(turn))
    if current is not None:
        sims = [similitud(v, current) for v in vals]
        sims = [float(s) for s in sims if s is not None]
        if len(sims) >= 2 and min(sims) >= PROBE_CURRENT_HOMOGENEITY:
            return True, {"windows": len(vals), "reason": "coherente_con_prototipo", "min_similarity": min(sims)}
    mutual = []
    for i in range(len(vals)):
        for j in range(i + 1, len(vals)):
            s = similitud(vals[i], vals[j])
            if s is not None:
                mutual.append(float(s))
    if mutual and float(np.median(mutual)) >= PROBE_MUTUAL_HOMOGENEITY:
        return True, {"windows": len(vals), "reason": "ventanas_mutuamente_coherentes", "median_mutual": float(np.median(mutual))}
    return False, {"windows": len(vals), "reason": "heterogeneo", "median_mutual": float(np.median(mutual)) if mutual else None}


def escanear_cambios_locales(turnos, embed_interval: EmbedInterval, *, allow_new_identities: bool, enabled: bool):
    """Sonda 3 ventanas; escaneo detallado solo si la sonda es sospechosa."""
    base_turns = [dict(t) for t in turnos]
    if not enabled:
        return base_turns, {"enabled": False, "reason": "resultado_no_sospechoso", "scanned_turns": 0, "applied_changes": 0}

    trusted_emb: Dict[int, Embedding] = {}
    for i, t in enumerate(base_turns):
        if MIN_EMBED_SECONDS <= _dur(t) < LOCAL_SCAN_MIN_SECONDS:
            e = normalizar(embed_interval(float(t["start"]), float(t["end"])))
            if e is not None:
                trusted_emb[i] = e
    protos = construir_prototipos(base_turns, trusted_emb)

    all_long = [i for i, t in enumerate(base_turns) if _dur(t) >= LOCAL_SCAN_MIN_SECONDS]
    eligible = [i for i in all_long if base._overlap_ratio(base_turns[i], base_turns) <= 0.15]
    eligible = sorted(eligible, key=lambda i: _dur(base_turns[i]), reverse=True)[:base.LOCAL_MAX_TURNS]
    detailed = []
    probe_meta = []
    for idx in eligible:
        homogeneous, info = _probe_homogeneous(base_turns[idx], protos, embed_interval)
        info = dict(info); info["turn_index"] = int(idx); info["homogeneous"] = bool(homogeneous)
        probe_meta.append(info)
        if not homogeneous:
            detailed.append(idx)

    if not detailed:
        return base_turns, {
            "enabled": True, "probe_turns": len(eligible), "probe_skipped_turns": len(eligible),
            "detailed_scanned_turns": 0, "scanned_turns": len(eligible),
            "eligible_turns": len(eligible), "scan_capped": len(all_long) > len(eligible),
            "candidate_runs": 0, "applied_changes": 0,
            "turns_before": len(base_turns), "turns_after": len(base_turns),
            "probes": probe_meta,
        }

    # Para reutilizar la lógica robusta V5.1 sin pagar por los turnos que la
    # sonda declaró homogéneos, hacemos que solo los sospechosos superen
    # temporalmente el umbral de duración. Los timestamps reales se conservan.
    marked = []
    detailed_set = set(detailed)
    for i, t in enumerate(base_turns):
        x = dict(t)
        if i in eligible and i not in detailed_set:
            x["_v52_skip_local"] = True
        marked.append(x)

    # Reimplementación acotada del escaneo para respetar detailed_set.
    next_id = max([_sp(t) for t in marked] + [-1]) + 1
    out: List[Dict[str, Any]] = []
    applied = candidate_runs = 0
    for idx, turn in enumerate(marked):
        if idx not in detailed_set:
            x = dict(turn); x.pop("_v52_skip_local", None); out.append(x); continue
        start, end = float(turn.get("start", 0.0)), float(turn.get("end", 0.0))
        intervals = base._window_intervals(start, end, base.LOCAL_WINDOW_SECONDS, base.LOCAL_MAX_WINDOWS)
        if len(intervals) < base.LOCAL_REQUIRED_WINDOWS:
            out.append(dict(turn)); continue
        labels, win_embs = [], []
        current_sp = _sp(turn)
        for a, b in intervals:
            e = normalizar(embed_interval(a, b)); win_embs.append(e)
            if e is None:
                labels.append((None, 0.0, 0.0)); continue
            current = similitud(e, protos.get(current_sp)) if protos.get(current_sp) is not None else None
            current_val = float(current) if current is not None else -1.0
            best_sp, best, _second = base._best_other(e, current_sp, protos)
            if best_sp is not None and best >= base.LOCAL_MATCH_THRESHOLD and best-current_val >= base.LOCAL_MATCH_MARGIN and current_val <= base.LOCAL_CURRENT_MAX:
                labels.append((int(best_sp), best, current_val))
            elif protos.get(current_sp) is not None and current_val <= base.LOCAL_UNKNOWN_CURRENT_MAX and best < base.LOCAL_UNKNOWN_RIVAL_MAX:
                labels.append(("unknown", best, current_val))
            elif protos.get(current_sp) is None and best < base.LOCAL_UNKNOWN_RIVAL_MAX:
                labels.append(("unknown", best, current_val))
            else:
                labels.append((current_sp, current_val, current_val))

        runs, i = [], 0
        while i < len(labels):
            label, j = labels[i][0], i + 1
            while j < len(labels) and labels[j][0] == label:
                j += 1
            if label != current_sp and label is not None and j-i >= base.LOCAL_REQUIRED_WINDOWS:
                runs.append((i, j, label))
            i = j
        if not runs:
            out.append(dict(turn)); continue

        pieces, cursor = [], start
        for i0, i1, label in runs:
            a, b = intervals[i0][0], intervals[i1-1][1]
            if a-cursor >= 0.40:
                pieces.append((cursor, a, current_sp))
            target = None
            if label == "unknown":
                vals = [win_embs[k] for k in range(i0, i1) if win_embs[k] is not None]
                mutual = []
                for x in range(len(vals)):
                    for y in range(x+1, len(vals)):
                        s = similitud(vals[x], vals[y])
                        if s is not None:
                            mutual.append(s)
                if allow_new_identities and vals and (not mutual or float(np.median(mutual)) >= base.LOCAL_UNKNOWN_MUTUAL_MIN) and b-a >= base.NEW_IDENTITY_MIN_SECONDS:
                    target = next_id; next_id += 1
            else:
                target = int(label)
            if target is not None:
                pieces.append((a, b, target)); applied += 1; candidate_runs += 1; cursor = b
            else:
                if b-cursor >= 0.40:
                    pieces.append((cursor, b, current_sp))
                cursor = b
        if end-cursor >= 0.40:
            pieces.append((cursor, end, current_sp))
        if not pieces:
            out.append(dict(turn)); continue
        for a, b, sp in pieces:
            x = dict(turn); x.pop("_v52_skip_local", None)
            x["start"] = float(a); x["end"] = float(b); x["speaker"] = int(sp)
            out.append(x)

    out.sort(key=lambda t: (float(t.get("start", 0.0)), float(t.get("end", 0.0)), int(t.get("speaker", 0))))
    return out, {
        "enabled": True, "probe_turns": len(eligible),
        "probe_skipped_turns": len(eligible) - len(detailed),
        "detailed_scanned_turns": len(detailed), "scanned_turns": len(eligible),
        "eligible_turns": len(eligible), "scan_capped": len(all_long) > len(eligible),
        "candidate_runs": candidate_runs, "applied_changes": applied,
        "turns_before": len(turnos), "turns_after": len(out), "probes": probe_meta,
    }
