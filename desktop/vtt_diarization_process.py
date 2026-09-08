#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Aislamiento de diarización en un proceso separado.

`sherpa-onnx` ejecuta la diarización en código nativo. Ejecutarlo en el mismo
intérprete puede impedir que Tkinter atienda eventos mientras dura `process()`.
Este módulo mantiene esa carga en un proceso hijo y deja al proceso de la UI
responsivo.
"""
from __future__ import annotations

import multiprocessing as mp
import queue
import time
import traceback
from pathlib import Path
from typing import Callable, Dict, List, Optional

import vtt_diarization as diar


class DiarizacionCancelada(Exception):
    """La diarización fue cancelada por el usuario."""


def estimar_restante(porcentaje: float, transcurrido: float) -> Optional[float]:
    """ETA simple en segundos usando el avance observado."""
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
    cola,
) -> None:
    """Punto de entrada del proceso hijo; solo usa datos serializables."""
    try:
        turnos = diar.diarizar(
            ruta,
            Path(carpeta_modelos),
            num_speakers=num_speakers,
            threshold=threshold,
            log=lambda texto: cola.put(("log", str(texto))),
            progreso=lambda pct: cola.put(("progress", float(pct))),
        )
        cola.put(("result", turnos))
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
) -> List[Dict]:
    """Ejecuta diarización en un proceso independiente.

    El hilo llamador permanece libre para vigilar cancelación y transmitir
    progreso; el proceso principal de Tkinter no queda secuestrado por el
    binding nativo de sherpa-onnx.
    """
    log = log or (lambda _: None)
    progreso = progreso or (lambda _: None)
    cancelado = cancelado or (lambda: False)

    ctx = mp.get_context("spawn")
    cola = ctx.Queue()
    proc = ctx.Process(
        target=_worker_diarizacion,
        args=(str(ruta), str(carpeta_modelos), int(num_speakers), float(threshold), cola),
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
                resultado = list(valor)
            elif tipo == "error":
                error = str(valor)

            if resultado is not None or error is not None:
                proc.join(timeout=2)
                break

        if resultado is not None:
            progreso(100.0)
            return resultado
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
