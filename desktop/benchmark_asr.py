#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Benchmark ASR reproducible para VtT.

Uso:
    python benchmark_asr.py "archivo.webm" --language es

Compara exactamente las cuatro combinaciones usadas para decidir el perfil de
rendimiento. Reutiliza cada modelo entre sus dos perfiles y guarda JSON + CSV.
Por defecto activa timestamps por palabra porque VtT los fuerza internamente
cuando identifica hablantes; así el tiempo medido es comparable con ese flujo.
No intenta decidir exactitud absoluta sin ground truth: la similitud textual
respecto de medium/Preciso es solo un indicador comparativo.
"""
from __future__ import annotations

import argparse
import csv
import difflib
import json
import time
from pathlib import Path

from vtt_performance import ASR_BENCHMARK_MATRIX


RUNTIME = {
    "Preciso": {"batch_size": 4, "beam_size": 5},
    "Equilibrado": {"batch_size": 8, "beam_size": 5},
}


def _normalize(text: str) -> str:
    return " ".join((text or "").lower().split())


def _similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, _normalize(a), _normalize(b)).ratio()


def benchmark(
    path: Path, language: str = "es", vad: bool = True,
    word_timestamps: bool = True,
):
    from faster_whisper import BatchedInferencePipeline, WhisperModel

    results = []
    loaded = {}
    for model_name, profile in ASR_BENCHMARK_MATRIX:
        load_seconds = 0.0
        if model_name not in loaded:
            t0 = time.perf_counter()
            loaded[model_name] = WhisperModel(
                model_name, device="cpu", compute_type="int8"
            )
            load_seconds = time.perf_counter() - t0
        model = loaded[model_name]
        pipeline = BatchedInferencePipeline(model=model)
        cfg = RUNTIME[profile]
        t0 = time.perf_counter()
        segments, info = pipeline.transcribe(
            str(path), language=language, vad_filter=vad,
            word_timestamps=bool(word_timestamps),
            beam_size=int(cfg["beam_size"]),
            batch_size=int(cfg["batch_size"]),
        )
        text = " ".join(s.text.strip() for s in segments if s.text.strip())
        elapsed = time.perf_counter() - t0
        duration = float(info.duration or 0.0)
        results.append({
            "model": model_name, "profile": profile,
            "batch_size": int(cfg["batch_size"]),
            "beam_size": int(cfg["beam_size"]),
            "word_timestamps": bool(word_timestamps),
            "model_load_seconds": load_seconds, "asr_seconds": elapsed,
            "audio_seconds": duration,
            "speed_x": duration / elapsed if elapsed > 0 else None,
            "text": text,
        })
    baseline = next(
        (r for r in results
         if r["model"] == "medium" and r["profile"] == "Preciso"),
        results[0],
    )
    for r in results:
        r["text_similarity_to_medium_preciso"] = _similarity(
            r["text"], baseline["text"]
        )
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio", type=Path)
    ap.add_argument("--language", default="es")
    ap.add_argument("--no-vad", action="store_true")
    ap.add_argument(
        "--without-word-timestamps", action="store_true",
        help="Mide ASR puro; por defecto imita el flujo con diarización.",
    )
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()
    if not args.audio.exists():
        raise SystemExit(f"No existe: {args.audio}")
    rows = benchmark(
        args.audio, args.language, not args.no_vad,
        word_timestamps=not args.without_word_timestamps,
    )
    stem = args.output or args.audio.with_name(
        args.audio.stem + "_benchmark_asr.json"
    )
    json_path = stem if stem.suffix.lower() == ".json" else stem.with_suffix(".json")
    csv_path = json_path.with_suffix(".csv")
    json_path.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    fields = [
        "model", "profile", "batch_size", "beam_size", "word_timestamps",
        "model_load_seconds", "asr_seconds", "audio_seconds", "speed_x",
        "text_similarity_to_medium_preciso",
    ]
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in fields})
    print(f"JSON: {json_path}")
    print(f"CSV:  {csv_path}")
    for r in rows:
        print(
            f"{r['model']:6} / {r['profile']:11}  "
            f"ASR {r['asr_seconds']:.1f}s  {(r['speed_x'] or 0):.2f}x  "
            f"similitud {r['text_similarity_to_medium_preciso']:.3f}"
        )


if __name__ == "__main__":
    main()
