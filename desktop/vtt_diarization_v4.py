#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Diarización V4: perfiles de velocidad y Auto estructural.

Mantiene el backend local sherpa-onnx, descarga/integridad de modelos y
reducción por regiones de V3. Añade:
- perfiles Rápida / Equilibrada / Precisa mediante window_shift_ratio;
- evaluación de distribución de turnos;
- segunda pasada Auto solo cuando el resultado es sospechoso;
- selección entre candidatos por una penalización estructural explícita.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

import vtt_diarization as legacy
import vtt_diarization_adaptive as v3

DIARIZATION_PROFILES: Dict[str, Dict[str, Any]] = {
    "Rápida": {
        "window_shift_ratio": 0.25,
        "description": "Menos ventanas de segmentación; prioriza velocidad.",
    },
    "Equilibrada": {
        "window_shift_ratio": 0.20,
        "description": "Compromiso entre tiempo de proceso y separación de voces.",
    },
    "Precisa": {
        "window_shift_ratio": 0.10,
        "description": "Resolución temporal de referencia de sherpa-onnx.",
    },
}

AUTO_INITIAL_THRESHOLD = 0.74
AUTO_SPLIT_THRESHOLD = 0.68
AUTO_MERGE_THRESHOLD = 0.82
AUTO_MAX_SPEAKERS = 8


def perfil_diarizacion(nombre: str) -> Tuple[str, Dict[str, Any]]:
    n = str(nombre or "Equilibrada").strip().capitalize()
    if n not in DIARIZATION_PROFILES:
        n = "Equilibrada"
    return n, dict(DIARIZATION_PROFILES[n])


def _crear(sherpa, seg_model: Path, emb_model: Path, num_speakers: int,
           threshold: float, threads: int, window_shift_ratio: float):
    cfg = sherpa.OfflineSpeakerDiarizationConfig(
        segmentation=sherpa.OfflineSpeakerSegmentationModelConfig(
            pyannote=sherpa.OfflineSpeakerSegmentationPyannoteModelConfig(
                model=str(seg_model), window_shift_ratio=float(window_shift_ratio)
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
    span = max(0.0, float(p1) - float(p0))

    def callback(done: int, total: int) -> int:
        if total:
            frac = min(1.0, max(0.0, float(done) / float(total)))
            progreso(float(p0) + span * frac)
        return 0

    result = sd.process(audio, callback=callback).sort_by_start_time()
    progreso(float(p1))
    return [
        {"start": float(x.start), "end": float(x.end), "speaker": int(x.speaker)}
        for x in result
        if float(x.end) > float(x.start)
    ]


def _fusionar_contiguos(turnos: Sequence[Dict[str, Any]], gap: float = 0.55):
    orden = sorted(
        (dict(t) for t in turnos if float(t.get("end", 0)) > float(t.get("start", 0))),
        key=lambda x: (float(x["start"]), float(x["end"])),
    )
    out: List[Dict[str, Any]] = []
    for t in orden:
        if (
            out
            and int(out[-1]["speaker"]) == int(t["speaker"])
            and float(t["start"]) - float(out[-1]["end"]) <= float(gap)
        ):
            out[-1]["end"] = max(float(out[-1]["end"]), float(t["end"]))
        else:
            out.append(dict(t))
    return out


def analizar_turnos(turnos: Sequence[Dict[str, Any]], audio_seconds: float) -> Dict[str, Any]:
    """Resume estructura de hablantes sin usar el texto transcrito."""
    fusionados = _fusionar_contiguos(turnos)
    dur_audio = max(0.0, float(audio_seconds or 0.0))
    por_hablante: Dict[int, float] = {}
    for t in fusionados:
        sp = int(t["speaker"])
        por_hablante[sp] = por_hablante.get(sp, 0.0) + max(
            0.0, float(t["end"]) - float(t["start"])
        )
    total_voz = sum(por_hablante.values())
    n = len(por_hablante)
    shares = {
        sp: (dur / total_voz if total_voz > 0 else 0.0)
        for sp, dur in por_hablante.items()
    }
    dominante = max(shares.values(), default=0.0)
    max_turno = max(
        (float(t["end"]) - float(t["start"]) for t in fusionados),
        default=0.0,
    )
    diminutos = sum(
        1
        for sp, dur in por_hablante.items()
        if dur < 3.0 or shares.get(sp, 0.0) < 0.02
    )
    minutos = max(dur_audio / 60.0, total_voz / 60.0, 1 / 60)
    cambios_min = max(0, len(fusionados) - 1) / minutos

    penalty = 0.0
    if n <= 1:
        penalty += 8.0
    elif n > AUTO_MAX_SPEAKERS:
        penalty += 2.0 * (n - AUTO_MAX_SPEAKERS)
    penalty += max(0.0, dominante - 0.65) * 4.0
    penalty += max(0.0, max_turno - 60.0) / 60.0
    penalty += diminutos * 0.8
    penalty += max(0.0, cambios_min - 16.0) / 8.0
    if n == 2 and dominante >= 0.80:
        penalty += 1.0

    return {
        "speaker_count": n,
        "turn_count": len(fusionados),
        "speech_seconds": total_voz,
        "dominant_share": dominante,
        "longest_turn_seconds": max_turno,
        "tiny_speakers": diminutos,
        "switches_per_minute": cambios_min,
        "penalty": penalty,
    }


def decidir_reintento(analisis: Dict[str, Any]) -> Tuple[Optional[float], Optional[str]]:
    n = int(analisis.get("speaker_count", 0) or 0)
    dominante = float(analisis.get("dominant_share", 0.0) or 0.0)
    largo = float(analisis.get("longest_turn_seconds", 0.0) or 0.0)
    tiny = int(analisis.get("tiny_speakers", 0) or 0)
    cambios = float(analisis.get("switches_per_minute", 0.0) or 0.0)

    if n <= 1:
        return AUTO_SPLIT_THRESHOLD, "subdeteccion_extrema"
    if n > AUTO_MAX_SPEAKERS:
        return AUTO_MERGE_THRESHOLD, "sobredeteccion_extrema"
    if tiny >= 2 or cambios > 18.0:
        return AUTO_MERGE_THRESHOLD, "fragmentacion_excesiva"
    if n <= 4 and (largo >= 60.0 or (largo >= 45.0 and dominante >= 0.55)):
        return AUTO_SPLIT_THRESHOLD, "tramo_monopolizado"
    if n <= 4 and dominante >= 0.72:
        return AUTO_SPLIT_THRESHOLD, "hablante_dominante"
    return None, None


def elegir_candidato(
    primero: Tuple[List[Dict[str, Any]], Dict[str, Any]],
    segundo: Tuple[List[Dict[str, Any]], Dict[str, Any]],
    motivo: str,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any], str]:
    turnos_a, a = primero
    turnos_b, b = segundo
    n_a = int(a.get("speaker_count", 0) or 0)
    n_b = int(b.get("speaker_count", 0) or 0)
    score_a = float(a.get("penalty", 0.0) or 0.0)
    score_b = float(b.get("penalty", 0.0) or 0.0)
    delta = abs(n_b - n_a)
    score_b_aj = score_b + max(0, delta - 2) * 0.25

    extremo = motivo in {"subdeteccion_extrema", "sobredeteccion_extrema"}
    if extremo:
        elegir_b = (
            2 <= n_b <= AUTO_MAX_SPEAKERS
            and score_b_aj <= score_a + 0.50
        )
    else:
        elegir_b = score_b_aj + 0.10 < score_a

    if elegir_b:
        return turnos_b, b, "segunda_pasada_mejora_estructura"
    return turnos_a, a, "se_conserva_primera_pasada"


def diarizar(
    ruta: str,
    carpeta_modelos: Path,
    num_speakers: int = -1,
    threshold: float = 0.5,
    log: Optional[Callable[[str], None]] = None,
    progreso: Optional[Callable[[float], None]] = None,
    speech_regions: Optional[Sequence[Sequence[float]]] = None,
    adaptive: bool = False,
    diar_profile: str = "Equilibrada",
    return_meta: bool = False,
) -> Union[List[Dict[str, Any]], Tuple[List[Dict[str, Any]], Dict[str, Any]]]:
    log = log or (lambda _: None)
    progreso = progreso or (lambda _: None)
    import sherpa_onnx as sherpa

    nombre_perfil, cfg_perfil = perfil_diarizacion(diar_profile)
    shift = float(cfg_perfil["window_shift_ratio"])
    seg_model, emb_model = legacy.asegurar_modelos(carpeta_modelos, log)
    threads = v3.hilos_diarizacion()
    initial_th = AUTO_INITIAL_THRESHOLD if adaptive and num_speakers < 0 else float(threshold)

    sd = _crear(
        sherpa, seg_model, emb_model, num_speakers, initial_th, threads, shift
    )
    progreso(2.0)
    log("Decodificando audio para identificar hablantes…")
    original = legacy.decodificar_audio_mono(ruta, int(sd.sample_rate))
    sr = int(sd.sample_rate)
    audio_seconds = len(original) / sr if sr else 0.0
    progreso(5.0)

    audio, mapa, reduccion = v3._reducir(original, sr, speech_regions or [])
    if reduccion.get("enabled"):
        log(
            f"Diarización sobre regiones de voz: {reduccion['coverage']*100:.0f}% "
            f"del audio ({reduccion['regions']} regiones)."
        )
    else:
        log("Diarización sobre audio completo (sin ahorro seguro por regiones).")
    log(
        f"Perfil de diarización {nombre_perfil}: window shift {shift:.2f} · "
        f"{threads} hilo(s)."
    )

    meta: Dict[str, Any] = {
        "adaptive": bool(adaptive and num_speakers < 0),
        "requested_speakers": None if num_speakers < 0 else int(num_speakers),
        "speech_region_reduction": reduccion,
        "selected_threshold": None,
        "retry": False,
        "passes": 1,
        "num_threads": threads,
        "diarization_profile": nombre_perfil,
        "window_shift_ratio": shift,
        "selection_reason": "manual" if num_speakers >= 0 else "primera_pasada_estable",
        "candidates": [],
    }

    if adaptive and num_speakers < 0:
        meta["selected_threshold"] = initial_th
        log(f"Auto: primera pasada (umbral {initial_th:.2f}).")
        turnos_a = _ejecutar(sd, audio, progreso, 5.0, 50.0)
        turnos_a = v3._remap(turnos_a, mapa)
        a = analizar_turnos(turnos_a, audio_seconds)
        meta["candidates"].append({"threshold": initial_th, "analysis": a})
        retry_th, motivo = decidir_reintento(a)

        if retry_th is not None:
            meta["retry"] = True
            meta["passes"] = 2
            log(
                "Auto: resultado estructuralmente sospechoso "
                f"({motivo}); segunda pasada con umbral {retry_th:.2f}."
            )
            sd2 = _crear(
                sherpa, seg_model, emb_model, -1, retry_th, threads, shift
            )
            turnos_b = _ejecutar(sd2, audio, progreso, 50.0, 100.0)
            turnos_b = v3._remap(turnos_b, mapa)
            b = analizar_turnos(turnos_b, audio_seconds)
            meta["candidates"].append({"threshold": retry_th, "analysis": b})
            turnos, elegido, razon = elegir_candidato(
                (turnos_a, a), (turnos_b, b), motivo
            )
            if turnos is turnos_b:
                meta["selected_threshold"] = retry_th
            meta["selection_reason"] = razon
            meta["retry_reason"] = motivo
            meta["selected_analysis"] = elegido
            meta["stability_delta_speakers"] = abs(
                int(a.get("speaker_count", 0)) - int(b.get("speaker_count", 0))
            )
            log(
                "Auto: selección final "
                f"{int(elegido.get('speaker_count', 0))} hablante(s) · {razon}."
            )
        else:
            progreso(100.0)
            turnos = turnos_a
            meta["selected_analysis"] = a
            meta["selection_reason"] = "primera_pasada_estable"
    else:
        meta["selected_threshold"] = None if num_speakers >= 0 else float(threshold)
        turnos = _ejecutar(sd, audio, progreso, 5.0, 100.0)
        turnos = v3._remap(turnos, mapa)
        analisis = analizar_turnos(turnos, audio_seconds)
        meta["selected_analysis"] = analisis
        meta["candidates"].append(
            {"threshold": meta["selected_threshold"], "analysis": analisis}
        )

    meta["detected_speakers"] = len(
        {int(t["speaker"]) for t in turnos}
    )
    meta["turns"] = len(turnos)
    progreso(100.0)
    return (turnos, meta) if return_meta else turnos
