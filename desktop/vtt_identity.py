#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Refinamiento acústico de identidades de hablante para VtT V5.1.

La lógica de decisión es independiente de sherpa-onnx: recibe embeddings por
turno y un callback para calcular embeddings adicionales durante el escaneo
local. Una intervención breve nunca se fusiona solo por su duración.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

# Calibración conservadora con los audios oficiales de 2 y 4 hablantes de
# sherpa-onnx usando el mismo modelo 3D-Speaker de VtT. En esas muestras los
# pares del mismo hablante bajaron hasta ~0.45 y los distintos no superaron
# ~0.33. Son referencias de ingeniería, no umbrales biométricos universales.
PAIR_INCONSISTENT_THRESHOLD = 0.35
OTHER_MATCH_THRESHOLD = 0.55
OTHER_MATCH_MARGIN = 0.12
MICRO_MERGE_THRESHOLD = 0.62
MICRO_MERGE_MARGIN = 0.10
NEW_IDENTITY_CURRENT_MAX = 0.35
NEW_IDENTITY_RIVAL_MAX = 0.45
NEW_IDENTITY_MIN_SECONDS = 2.5
MIN_EMBED_SECONDS = 0.80

LOCAL_SCAN_MIN_SECONDS = 18.0
LOCAL_WINDOW_SECONDS = 2.5
LOCAL_MAX_WINDOWS = 6
LOCAL_MAX_TURNS = 4
LOCAL_MATCH_THRESHOLD = 0.58
LOCAL_MATCH_MARGIN = 0.15
LOCAL_CURRENT_MAX = 0.50
LOCAL_UNKNOWN_CURRENT_MAX = 0.35
LOCAL_UNKNOWN_RIVAL_MAX = 0.45
LOCAL_UNKNOWN_MUTUAL_MIN = 0.55
LOCAL_REQUIRED_WINDOWS = 2

Embedding = np.ndarray
EmbedInterval = Callable[[float, float], Optional[Embedding]]


def normalizar(v: Any) -> Optional[Embedding]:
    if v is None:
        return None
    try:
        x = np.asarray(v, dtype=np.float32).reshape(-1)
    except Exception:
        return None
    if not x.size or not np.all(np.isfinite(x)):
        return None
    n = float(np.linalg.norm(x))
    if n <= 0:
        return None
    return x / n


def similitud(a: Any, b: Any) -> Optional[float]:
    x, y = normalizar(a), normalizar(b)
    if x is None or y is None or x.shape != y.shape:
        return None
    return float(np.clip(np.dot(x, y), -1.0, 1.0))


def _dur(t: Mapping[str, Any]) -> float:
    try:
        return max(0.0, float(t.get("end", 0.0)) - float(t.get("start", 0.0)))
    except (TypeError, ValueError):
        return 0.0


def _sp(t: Mapping[str, Any]) -> int:
    return int(t.get("speaker", 0))


def _grupos(turnos: Sequence[Mapping[str, Any]], embeddings: Mapping[int, Embedding]):
    out: Dict[int, List[int]] = {}
    for i, t in enumerate(turnos):
        if i in embeddings:
            out.setdefault(_sp(t), []).append(i)
    return out


def _prototype(indices: Sequence[int], embeddings: Mapping[int, Embedding]) -> Optional[Embedding]:
    vals = [normalizar(embeddings.get(i)) for i in indices]
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    if len(vals) == 1:
        return vals[0]
    scores = []
    for i, v in enumerate(vals):
        sims = [float(np.dot(v, w)) for j, w in enumerate(vals) if j != i]
        scores.append(float(np.median(sims)) if sims else 1.0)
    medoid = vals[int(np.argmax(np.asarray(scores)))]
    cercanos = sorted(vals, key=lambda v: float(np.dot(v, medoid)), reverse=True)
    return normalizar(np.mean(cercanos[: min(3, len(cercanos))], axis=0))


def construir_prototipos(turnos: Sequence[Mapping[str, Any]], embeddings: Mapping[int, Embedding]):
    grupos = _grupos(turnos, embeddings)
    return {sp: _prototype(idxs, embeddings) for sp, idxs in grupos.items()}


def _best_other(e: Embedding, current: int, protos: Mapping[int, Optional[Embedding]]):
    vals = []
    for sp, p in protos.items():
        if sp == current or p is None:
            continue
        s = similitud(e, p)
        if s is not None:
            vals.append((float(s), int(sp)))
    vals.sort(reverse=True)
    best = vals[0] if vals else (-1.0, None)
    second = vals[1][0] if len(vals) > 1 else -1.0
    return best[1], float(best[0]), float(second)


def _pair_similarity(indices: Sequence[int], embeddings: Mapping[int, Embedding]) -> Optional[float]:
    if len(indices) != 2:
        return None
    return similitud(embeddings.get(indices[0]), embeddings.get(indices[1]))


def _anchor_two(turnos, indices):
    a, b = indices
    da, db = _dur(turnos[a]), _dur(turnos[b])
    if da > db * 1.35:
        return a, b
    if db > da * 1.35:
        return b, a
    if float(turnos[a].get("start", 0.0)) <= float(turnos[b].get("start", 0.0)):
        return a, b
    return b, a


def _cluster_new_candidates(candidates, embeddings, turnos, next_id):
    remaining = list(candidates)
    mapping: Dict[int, int] = {}
    while remaining:
        seed = remaining.pop(0)
        group = [seed]
        rest = []
        for idx in remaining:
            s = similitud(embeddings.get(seed), embeddings.get(idx))
            if s is not None and s >= OTHER_MATCH_THRESHOLD:
                group.append(idx)
            else:
                rest.append(idx)
        remaining = rest
        total = sum(_dur(turnos[i]) for i in group)
        longest = max((_dur(turnos[i]) for i in group), default=0.0)
        if total >= NEW_IDENTITY_MIN_SECONDS or longest >= NEW_IDENTITY_MIN_SECONDS:
            for idx in group:
                mapping[idx] = next_id
            next_id += 1
    return mapping, next_id


def refinar_turnos(turnos, embeddings, *, allow_new_identities: bool = True):
    """Corrige reutilizaciones incoherentes y microclusters solo con evidencia."""
    out = [dict(t) for t in turnos]
    before = sorted({_sp(t) for t in out})
    protos = construir_prototipos(out, embeddings)
    grupos = _grupos(out, embeddings)
    reassignments: List[Dict[str, Any]] = []
    new_candidates: List[int] = []

    # Un cluster de un turno se fusiona únicamente si coincide fuertemente con
    # otra identidad; su brevedad, por sí sola, nunca basta.
    for sp, idxs in grupos.items():
        if len(idxs) != 1:
            continue
        idx = idxs[0]
        best_sp, best, second = _best_other(embeddings[idx], sp, protos)
        if best_sp is not None and best >= MICRO_MERGE_THRESHOLD and best - second >= MICRO_MERGE_MARGIN:
            out[idx]["speaker"] = int(best_sp)
            reassignments.append({
                "turn_index": idx, "from": int(sp), "to": int(best_sp),
                "reason": "microcluster_matches_existing_identity", "similarity": best,
            })

    protos = construir_prototipos(out, embeddings)
    grupos = _grupos(out, embeddings)
    for sp, idxs in list(grupos.items()):
        if len(idxs) != 2:
            continue
        pair = _pair_similarity(idxs, embeddings)
        if pair is None or pair >= PAIR_INCONSISTENT_THRESHOLD:
            continue
        anchor, suspect = _anchor_two(out, idxs)
        best_sp, best, second = _best_other(embeddings[suspect], sp, protos)
        if best_sp is not None and best >= OTHER_MATCH_THRESHOLD and best - second >= OTHER_MATCH_MARGIN:
            out[suspect]["speaker"] = int(best_sp)
            reassignments.append({
                "turn_index": suspect, "from": int(sp), "to": int(best_sp),
                "reason": "two_turn_identity_conflict_reassigned",
                "pair_similarity": pair, "similarity": best,
                "anchor_turn_index": anchor,
            })
        elif allow_new_identities and _dur(out[suspect]) >= NEW_IDENTITY_MIN_SECONDS and best < NEW_IDENTITY_RIVAL_MAX:
            new_candidates.append(suspect)

    protos = construir_prototipos(out, embeddings)
    grupos = _grupos(out, embeddings)
    for sp, idxs in list(grupos.items()):
        if len(idxs) < 3:
            continue
        p = protos.get(sp)
        if p is None:
            continue
        for idx in idxs:
            current = similitud(embeddings[idx], p)
            if current is None or current >= 0.50:
                continue
            best_sp, best, second = _best_other(embeddings[idx], sp, protos)
            if best_sp is not None and best >= OTHER_MATCH_THRESHOLD and best - max(second, current) >= OTHER_MATCH_MARGIN:
                out[idx]["speaker"] = int(best_sp)
                reassignments.append({
                    "turn_index": idx, "from": int(sp), "to": int(best_sp),
                    "reason": "cluster_outlier_reassigned",
                    "current_similarity": current, "similarity": best,
                })
            elif allow_new_identities and current < NEW_IDENTITY_CURRENT_MAX and best < NEW_IDENTITY_RIVAL_MAX and _dur(out[idx]) >= NEW_IDENTITY_MIN_SECONDS:
                new_candidates.append(idx)

    next_id = max([_sp(t) for t in out] + [-1]) + 1
    new_map: Dict[int, int] = {}
    if allow_new_identities and new_candidates:
        unique, seen = [], set()
        for i in new_candidates:
            if i not in seen:
                seen.add(i); unique.append(i)
        new_map, next_id = _cluster_new_candidates(unique, embeddings, out, next_id)
        for idx, new_sp in new_map.items():
            old = _sp(out[idx]); out[idx]["speaker"] = int(new_sp)
            reassignments.append({
                "turn_index": idx, "from": int(old), "to": int(new_sp),
                "reason": "new_identity_from_inconsistent_turn",
            })

    after = sorted({_sp(t) for t in out})
    return out, {
        "speakers_before": len(before), "speakers_after": len(after),
        "reassignments": reassignments, "reassigned_turns": len(reassignments),
        "new_identity_turns": len(new_map), "new_identities": len(set(new_map.values())),
    }


def resumir_identidades(turnos, embeddings) -> Dict[str, Any]:
    protos = construir_prototipos(turnos, embeddings)
    grupos: Dict[int, List[int]] = {}
    for i, t in enumerate(turnos):
        grupos.setdefault(_sp(t), []).append(i)
    speakers = []
    low = medium = high = insufficient = 0
    for sp in sorted(grupos):
        idxs = sorted(grupos[sp], key=lambda i: float(turnos[i].get("start", 0.0)))
        emb_idxs = [i for i in idxs if i in embeddings]
        durations = [_dur(turnos[i]) for i in idxs]
        starts = [float(turnos[i].get("start", 0.0)) for i in idxs]
        gaps = [max(0.0, starts[i + 1] - float(turnos[idxs[i]].get("end", starts[i]))) for i in range(max(0, len(starts)-1))]
        pair = _pair_similarity(emb_idxs, embeddings) if len(emb_idxs) == 2 else None
        p = protos.get(sp)
        own, rivals = [], []
        for i in emb_idxs:
            if p is not None:
                s = similitud(embeddings[i], p)
                if s is not None:
                    own.append(s)
            _osp, best, _second = _best_other(embeddings[i], sp, protos)
            if best >= -0.5:
                rivals.append(best)
        if len(emb_idxs) == 0:
            label = "sin_datos"; insufficient += 1
        elif len(emb_idxs) == 1:
            label = "insuficiente"; insufficient += 1
        elif len(emb_idxs) == 2:
            if pair is not None and pair >= 0.50:
                label = "alta"; high += 1
            elif pair is not None and pair >= PAIR_INCONSISTENT_THRESHOLD:
                label = "media"; medium += 1
            else:
                label = "baja"; low += 1
        else:
            med = float(np.median(own)) if own else 0.0
            if med >= 0.78:
                label = "alta"; high += 1
            elif med >= 0.65:
                label = "media"; medium += 1
            else:
                label = "baja"; low += 1
        speakers.append({
            "speaker": int(sp), "turns": len(idxs), "embedded_turns": len(emb_idxs),
            "total_seconds": float(sum(durations)), "first_start": min(starts) if starts else None,
            "last_start": max(starts) if starts else None, "max_gap_seconds": max(gaps) if gaps else 0.0,
            "pair_similarity": pair, "prototype_similarity_min": min(own) if own else None,
            "prototype_similarity_median": float(np.median(own)) if own else None,
            "rival_similarity_max": max(rivals) if rivals else None,
            "confidence": label, "brief_identity": float(sum(durations)) < 3.0,
        })
    overall = "baja" if low else ("media" if medium or insufficient else ("alta" if speakers else "sin_datos"))
    return {
        "overall_confidence": overall, "low_confidence_speakers": low,
        "medium_confidence_speakers": medium, "high_confidence_speakers": high,
        "insufficient_speakers": insufficient, "speakers": speakers,
    }


def extraer_embeddings_turnos(turnos, embed_interval: EmbedInterval, *, min_seconds: float = MIN_EMBED_SECONDS, max_per_speaker: int = 8, max_total: int = 64):
    eligible_by_sp: Dict[int, List[int]] = {}
    skipped_short = skipped_long = 0
    for i, t in enumerate(turnos):
        d = _dur(t)
        if d < min_seconds:
            skipped_short += 1; continue
        # Un turno largo puede contener más de una voz; no se usa como prototipo.
        if d >= LOCAL_SCAN_MIN_SECONDS:
            skipped_long += 1; continue
        eligible_by_sp.setdefault(_sp(t), []).append(i)
    selected: List[int] = []
    for _spk, idxs in eligible_by_sp.items():
        ordered = sorted(idxs, key=lambda i: float(turnos[i].get("start", 0.0)))
        keep: List[int] = []
        if ordered:
            keep.extend([ordered[0], ordered[-1]])
        keep.extend(sorted(idxs, key=lambda i: _dur(turnos[i]), reverse=True)[:max_per_speaker])
        uniq, seen = [], set()
        for i in keep:
            if i not in seen:
                seen.add(i); uniq.append(i)
        selected.extend(uniq[:max_per_speaker])
    if len(selected) > max_total:
        selected = sorted(selected, key=lambda i: _dur(turnos[i]), reverse=True)[:max_total]
    selected = sorted(set(selected))
    out: Dict[int, Embedding] = {}
    attempted = 0
    for i in selected:
        t = turnos[i]; attempted += 1
        e = normalizar(embed_interval(float(t["start"]), float(t["end"])))
        if e is not None:
            out[i] = e
    eligible = sum(len(v) for v in eligible_by_sp.values())
    return out, {
        "eligible": eligible, "selected": len(selected), "attempted": attempted,
        "computed": len(out), "skipped_short": skipped_short, "skipped_long": skipped_long,
        "capped": eligible > len(selected),
    }


def _overlap_ratio(turn, others) -> float:
    a, b = float(turn.get("start", 0.0)), float(turn.get("end", 0.0))
    dur = max(0.0, b-a)
    if dur <= 0:
        return 0.0
    ov, sp = 0.0, _sp(turn)
    for t in others:
        if _sp(t) == sp:
            continue
        x, y = float(t.get("start", 0.0)), float(t.get("end", 0.0))
        ov += max(0.0, min(b, y)-max(a, x))
    return min(1.0, ov/dur)


def _window_intervals(start: float, end: float, seconds: float, max_windows: int):
    dur = max(0.0, end-start)
    if dur < seconds:
        return []
    n = min(max_windows, max(1, int(dur // seconds)))
    if n == 1:
        c = (start+end)/2.0
        return [(max(start, c-seconds/2), min(end, c+seconds/2))]
    centers = np.linspace(start+seconds/2, end-seconds/2, n)
    return [(float(c-seconds/2), float(c+seconds/2)) for c in centers]


def escanear_cambios_locales(turnos, embed_interval: EmbedInterval, *, allow_new_identities: bool, enabled: bool):
    base = [dict(t) for t in turnos]
    if not enabled:
        return base, {"enabled": False, "reason": "resultado_no_sospechoso", "scanned_turns": 0, "applied_changes": 0}

    # Prototipos de confianza: excluye turnos largos que precisamente se revisan.
    trusted_emb: Dict[int, Embedding] = {}
    for i, t in enumerate(base):
        if MIN_EMBED_SECONDS <= _dur(t) < LOCAL_SCAN_MIN_SECONDS:
            e = normalizar(embed_interval(float(t["start"]), float(t["end"])))
            if e is not None:
                trusted_emb[i] = e
    protos = construir_prototipos(base, trusted_emb)
    next_id = max([_sp(t) for t in base] + [-1]) + 1
    out: List[Dict[str, Any]] = []
    scanned = applied = candidate_runs = 0
    all_long = [i for i, t in enumerate(base) if _dur(t) >= LOCAL_SCAN_MIN_SECONDS]
    eligible = [i for i in all_long if _overlap_ratio(base[i], base) <= 0.15]
    eligible = set(sorted(eligible, key=lambda i: _dur(base[i]), reverse=True)[:LOCAL_MAX_TURNS])

    for idx, turn in enumerate(base):
        start, end = float(turn.get("start", 0.0)), float(turn.get("end", 0.0))
        if idx not in eligible:
            out.append(dict(turn)); continue
        intervals = _window_intervals(start, end, LOCAL_WINDOW_SECONDS, LOCAL_MAX_WINDOWS)
        if len(intervals) < LOCAL_REQUIRED_WINDOWS:
            out.append(dict(turn)); continue
        scanned += 1
        labels, win_embs = [], []
        current_sp = _sp(turn)
        for a, b in intervals:
            e = normalizar(embed_interval(a, b)); win_embs.append(e)
            if e is None:
                labels.append((None, 0.0, 0.0)); continue
            current = similitud(e, protos.get(current_sp)) if protos.get(current_sp) is not None else None
            current_val = float(current) if current is not None else -1.0
            best_sp, best, _second = _best_other(e, current_sp, protos)
            if best_sp is not None and best >= LOCAL_MATCH_THRESHOLD and best-current_val >= LOCAL_MATCH_MARGIN and current_val <= LOCAL_CURRENT_MAX:
                labels.append((int(best_sp), best, current_val))
            elif protos.get(current_sp) is not None and current_val <= LOCAL_UNKNOWN_CURRENT_MAX and best < LOCAL_UNKNOWN_RIVAL_MAX:
                labels.append(("unknown", best, current_val))
            else:
                labels.append((current_sp, current_val, current_val))

        runs, i = [], 0
        while i < len(labels):
            label, j = labels[i][0], i+1
            while j < len(labels) and labels[j][0] == label:
                j += 1
            if label != current_sp and label is not None and j-i >= LOCAL_REQUIRED_WINDOWS:
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
                if allow_new_identities and vals and (not mutual or float(np.median(mutual)) >= LOCAL_UNKNOWN_MUTUAL_MIN) and b-a >= NEW_IDENTITY_MIN_SECONDS:
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
            x = dict(turn); x["start"] = float(a); x["end"] = float(b); x["speaker"] = int(sp)
            out.append(x)

    out.sort(key=lambda t: (float(t.get("start", 0.0)), float(t.get("end", 0.0)), int(t.get("speaker", 0))))
    return out, {
        "enabled": True, "scanned_turns": scanned, "eligible_turns": len(eligible),
        "scan_capped": len(all_long) > len(eligible), "candidate_runs": candidate_runs,
        "applied_changes": applied, "turns_before": len(turnos), "turns_after": len(out),
    }
