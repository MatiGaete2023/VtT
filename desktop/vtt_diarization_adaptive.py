#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Diarización optimizada sobre el backend estable ``vtt_diarization``.

No duplica descarga/integridad de modelos. Añade:
- varios hilos CPU (el backend usa 1 por defecto);
- Auto equilibrado con corrección solo para conteos extremos;
- reducción opcional a regiones de voz y remapeo al tiempo original.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

import vtt_diarization as legacy
import vtt_tuning as tuning


def hilos_diarizacion() -> int:
    try:
        manual = int(os.environ.get("VTT_DIAR_THREADS", "0") or 0)
    except ValueError:
        manual = 0
    if manual > 0:
        return max(1, min(8, manual))
    return max(1, min(4, int(os.cpu_count() or 2)))


def _crear(sherpa, seg_model: Path, emb_model: Path,
           num_speakers: int, threshold: float, threads: int):
    cfg = sherpa.OfflineSpeakerDiarizationConfig(
        segmentation=sherpa.OfflineSpeakerSegmentationModelConfig(
            pyannote=sherpa.OfflineSpeakerSegmentationPyannoteModelConfig(
                model=str(seg_model), window_shift_ratio=0.1
            ),
            num_threads=int(threads),
        ),
        embedding=sherpa.SpeakerEmbeddingExtractorConfig(
            model=str(emb_model), num_threads=int(threads)
        ),
        clustering=sherpa.FastClusteringConfig(
            num_clusters=int(num_speakers), threshold=float(threshold)
        ),
        min_duration_on=0.3,
        min_duration_off=0.5,
    )
    if not cfg.validate():
        raise RuntimeError("Configuración de diarización inválida; revisa los modelos")
    return sherpa.OfflineSpeakerDiarization(cfg)


def _ejecutar(sd, audio, progreso, p0: float, p1: float):
    span = max(0.0, p1 - p0)
    def callback(done: int, total: int) -> int:
        if total:
            progreso(p0 + span * min(1.0, max(0.0, done / total)))
        return 0
    result = sd.process(audio, callback=callback).sort_by_start_time()
    progreso(p1)
    return [
        {"start": float(x.start), "end": float(x.end), "speaker": int(x.speaker)}
        for x in result if float(x.end) > float(x.start)
    ]


def _reducir(audio, sr: int, regiones: Sequence[Sequence[float]], sep_s: float = 0.25):
    import numpy as np
    if not regiones or sr <= 0:
        return audio, [], {"enabled": False, "reason": "sin_regiones", "coverage": 1.0}
    dur = len(audio) / sr
    validas = []
    for r in regiones:
        if len(r) < 2:
            continue
        a, b = max(0.0, float(r[0])), min(dur, float(r[1]))
        if b - a >= 0.05:
            validas.append((a, b))
    if len(validas) < 2:
        return audio, [], {"enabled": False, "reason": "regiones_insuficientes", "coverage": 1.0}

    silencio = np.zeros(max(1, int(round(sep_s * sr))), dtype=np.float32)
    piezas, mapa = [], []
    cursor = 0.0
    for i, (a, b) in enumerate(validas):
        ia, ib = int(round(a * sr)), int(round(b * sr))
        chunk = audio[max(0, ia):min(len(audio), ib)]
        if len(chunk) == 0:
            continue
        c0, c1 = cursor, cursor + len(chunk) / sr
        piezas.append(chunk)
        mapa.append({"concat_start": c0, "concat_end": c1, "original_start": a, "original_end": b})
        cursor = c1
        if i < len(validas) - 1:
            piezas.append(silencio)
            cursor += len(silencio) / sr
    if not mapa:
        return audio, [], {"enabled": False, "reason": "regiones_vacias", "coverage": 1.0}
    reducido = np.ascontiguousarray(np.concatenate(piezas))
    speech = sum(m["original_end"] - m["original_start"] for m in mapa)
    return reducido, mapa, {
        "enabled": True,
        "regions": len(mapa),
        "audio_seconds": dur,
        "speech_seconds": speech,
        "processed_seconds": len(reducido) / sr,
        "coverage": speech / dur if dur else 1.0,
        "saved_seconds": max(0.0, dur - speech),
        "separator_seconds": sep_s,
    }


def _remap(turnos: Sequence[Dict[str, Any]], mapa: Sequence[Dict[str, float]]):
    if not mapa:
        return [dict(t) for t in turnos]
    out = []
    for t in turnos:
        t0, t1 = float(t["start"]), float(t["end"])
        for m in mapa:
            a, b = max(t0, m["concat_start"]), min(t1, m["concat_end"])
            if b - a < 0.05:
                continue
            out.append({
                "start": m["original_start"] + a - m["concat_start"],
                "end": m["original_start"] + b - m["concat_start"],
                "speaker": int(t["speaker"]),
            })
    out.sort(key=lambda x: (x["start"], x["end"]))
    merged = []
    for t in out:
        if merged and merged[-1]["speaker"] == t["speaker"] and t["start"] - merged[-1]["end"] <= 0.20:
            merged[-1]["end"] = max(merged[-1]["end"], t["end"])
        else:
            merged.append(dict(t))
    return merged


def diarizar(
    ruta: str,
    carpeta_modelos: Path,
    num_speakers: int = -1,
    threshold: float = 0.5,
    log: Optional[Callable[[str], None]] = None,
    progreso: Optional[Callable[[float], None]] = None,
    speech_regions: Optional[Sequence[Sequence[float]]] = None,
    adaptive: bool = False,
    return_meta: bool = False,
) -> Union[List[Dict[str, Any]], Tuple[List[Dict[str, Any]], Dict[str, Any]]]:
    log = log or (lambda _: None)
    progreso = progreso or (lambda _: None)
    import sherpa_onnx as sherpa

    seg_model, emb_model = legacy.asegurar_modelos(carpeta_modelos, log)
    threads = hilos_diarizacion()
    initial_th = tuning.AUTO_BALANCED_THRESHOLD if adaptive and num_speakers < 0 else float(threshold)
    sd = _crear(sherpa, seg_model, emb_model, num_speakers, initial_th, threads)
    progreso(2.0)
    log("Decodificando audio para identificar hablantes…")
    original = legacy.decodificar_audio_mono(ruta, int(sd.sample_rate))
    sr = int(sd.sample_rate)
    progreso(5.0)

    audio, mapa, reduccion = _reducir(original, sr, speech_regions or [])
    if reduccion.get("enabled"):
        log(
            f"Diarización sobre regiones de voz: {reduccion['coverage']*100:.0f}% del audio "
            f"({reduccion['regions']} regiones)."
        )
    else:
        log("Diarización sobre audio completo (sin ahorro seguro por regiones).")
    log(f"Diarización CPU: {threads} hilo(s) de inferencia por modelo.")

    meta = {
        "adaptive": bool(adaptive and num_speakers < 0),
        "requested_speakers": None if num_speakers < 0 else int(num_speakers),
        "speech_region_reduction": reduccion,
        "selected_threshold": None,
        "retry": False,
        "num_threads": threads,
    }

    if adaptive and num_speakers < 0:
        meta["selected_threshold"] = initial_th
        log(f"Auto adaptativo: primera pasada equilibrada (umbral {initial_th:.2f}).")
        turnos = _ejecutar(sd, audio, progreso, 5.0, 85.0)
        n0 = len({int(t["speaker"]) for t in turnos})
        meta["initial_speakers"] = n0
        retry_th = tuning.ajuste_auto_por_conteo(n0)
        if retry_th is not None:
            meta["retry"] = True
            meta["selected_threshold"] = retry_th
            accion = "separar voces" if n0 <= 1 else "fusionar clusters"
            log(f"Auto adaptativo: resultado extremo ({n0}); segunda pasada {retry_th:.2f} para {accion}.")
            sd2 = _crear(sherpa, seg_model, emb_model, -1, retry_th, threads)
            turnos = _ejecutar(sd2, audio, progreso, 85.0, 100.0)
        else:
            progreso(100.0)
    else:
        meta["selected_threshold"] = None if num_speakers >= 0 else float(threshold)
        turnos = _ejecutar(sd, audio, progreso, 5.0, 100.0)

    turnos = _remap(turnos, mapa)
    meta["detected_speakers"] = len({int(t["speaker"]) for t in turnos})
    meta["turns"] = len(turnos)
    progreso(100.0)
    return (turnos, meta) if return_meta else turnos
