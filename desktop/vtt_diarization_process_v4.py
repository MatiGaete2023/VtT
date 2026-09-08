#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Proceso aislado para diarización V4."""
from __future__ import annotations

import multiprocessing as mp
import queue
import traceback
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

import vtt_diarization_v4 as diar


class DiarizacionCancelada(Exception):
    """La diarización fue cancelada por el usuario."""


def estimar_restante(porcentaje: float, transcurrido: float) -> Optional[float]:
    try:
        p = float(porcentaje)
        t = float(transcurrido)
    except (TypeError, ValueError):
        return None
    if p <= 0 or p >= 100 or t <= 0:
        return 0.0 if p >= 100 else None
    avance = p / 100.0
    return max(0.0, t / avance - t)


def _worker_diarizacion(
    ruta: str,
    carpeta_modelos: str,
    num_speakers: int,
    threshold: float,
    speech_regions: Optional[List[Tuple[float, float]]],
    adaptive: bool,
    diar_profile: str,
    cola,
) -> None:
    try:
        turnos, meta = diar.diarizar(
            ruta,
            Path(carpeta_modelos),
            num_speakers=num_speakers,
            threshold=threshold,
            log=lambda texto: cola.put(("log", str(texto))),
            progreso=lambda pct: cola.put(("progress", float(pct))),
            speech_regions=speech_regions,
            adaptive=bool(adaptive),
            diar_profile=str(diar_profile),
            return_meta=True,
        )
        cola.put(("result", {"turns": turnos, "meta": meta}))
    except BaseException:
        cola.put(("error", traceback.format_exc()))


def diarizar_responsivo(
    ruta: str,
    carpeta_modelos: Path,
    num_speakers: int = -1,
    threshold: float = 0.5,
    log: Optional[Callable[[str], None]] = None,
    progreso: Optional[Callable[[float], None]] = None,
    cancelado: Optional[Callable[[], bool]] = None,
    speech_regions: Optional[Sequence[Sequence[float]]] = None,
    adaptive: bool = False,
    diar_profile: str = "Equilibrada",
    return_meta: bool = False,
) -> Union[List[Dict], Tuple[List[Dict], Dict[str, Any]]]:
    log = log or (lambda _: None)
    progreso = progreso or (lambda _: None)
    cancelado = cancelado or (lambda: False)

    regiones_serializables: Optional[List[Tuple[float, float]]] = None
    if speech_regions:
        regiones_serializables = [
            (float(r[0]), float(r[1])) for r in speech_regions if len(r) >= 2
        ]

    ctx = mp.get_context("spawn")
    cola = ctx.Queue()
    proc = ctx.Process(
        target=_worker_diarizacion,
        args=(
            str(ruta),
            str(carpeta_modelos),
            int(num_speakers),
            float(threshold),
            regiones_serializables,
            bool(adaptive),
            str(diar_profile),
            cola,
        ),
        daemon=True,
    )
    proc.start()

    resultado = None
    error = None
    try:
        while True:
            if cancelado():
                if proc.is_alive():
                    proc.terminate()
                proc.join(timeout=3)
                raise DiarizacionCancelada()

            try:
                tipo, valor = cola.get(timeout=0.20)
            except queue.Empty:
                if not proc.is_alive():
                    break
                continue

            if tipo == "log":
                log(str(valor))
            elif tipo == "progress":
                progreso(float(valor))
            elif tipo == "result":
                if isinstance(valor, dict):
                    resultado = dict(valor)
                else:
                    resultado = {"turns": list(valor or []), "meta": {}}
            elif tipo == "error":
                error = str(valor)

            if resultado is not None or error is not None:
                proc.join(timeout=2)
                break

        if resultado is not None:
            progreso(100.0)
            turnos = list(resultado.get("turns") or [])
            meta = dict(resultado.get("meta") or {})
            return (turnos, meta) if return_meta else turnos
        if error is not None:
            raise RuntimeError("Falló la identificación de hablantes:\n" + error)
        if proc.exitcode not in (0, None):
            raise RuntimeError(
                f"El proceso de identificación de hablantes terminó con código {proc.exitcode}."
            )
        raise RuntimeError("La identificación de hablantes terminó sin devolver resultado.")
    finally:
        if proc.is_alive():
            proc.terminate()
            proc.join(timeout=2)
        try:
            cola.close()
            cola.join_thread()
        except Exception:
            pass
