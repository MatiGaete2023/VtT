#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Worker persistente V5.2 para diarización identity-aware."""
from __future__ import annotations

import multiprocessing as mp
import queue
import traceback
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import vtt_diarization_v52_metrics as diar52
from vtt_diarization_errors import DiarizacionCancelada


def _worker_loop(carpeta_modelos: str, comandos, eventos) -> None:
    engine = diar52.DiarizationEngine(Path(carpeta_modelos))
    while True:
        cmd = comandos.get()
        if not isinstance(cmd, dict):
            continue
        if cmd.get("cmd") == "stop":
            break
        if cmd.get("cmd") != "diarize":
            continue
        job_id = str(cmd.get("job_id"))
        try:
            turnos, meta = engine.diarize(
                str(cmd["ruta"]), num_speakers=int(cmd.get("num_speakers", -1)),
                threshold=float(cmd.get("threshold", 0.5)),
                speech_regions=cmd.get("speech_regions"),
                adaptive=bool(cmd.get("adaptive", False)),
                diar_profile=str(cmd.get("diar_profile", "Equilibrada")),
                time_budget_seconds=cmd.get("time_budget_seconds"),
                log=lambda texto: eventos.put((job_id, "log", str(texto))),
                progreso=lambda pct: eventos.put((job_id, "progress", float(pct))),
            )
            eventos.put((job_id, "result", {"turns": turnos, "meta": meta}))
        except BaseException:
            eventos.put((job_id, "error", traceback.format_exc()))


class PersistentDiarizationService:
    def __init__(self, carpeta_modelos: Path):
        self.carpeta_modelos = Path(carpeta_modelos)
        self.ctx = mp.get_context("spawn")
        self.proc = self.comandos = self.eventos = None
        self.counter = 0

    def _start(self) -> None:
        if self.proc is not None and self.proc.is_alive():
            return
        self.comandos, self.eventos = self.ctx.Queue(), self.ctx.Queue()
        self.proc = self.ctx.Process(
            target=_worker_loop,
            args=(str(self.carpeta_modelos), self.comandos, self.eventos), daemon=True,
        )
        self.proc.start()

    def _reset(self) -> None:
        proc = self.proc
        if proc is not None and proc.is_alive():
            proc.terminate(); proc.join(timeout=3)
        for q in (self.comandos, self.eventos):
            if q is not None:
                try: q.close(); q.join_thread()
                except Exception: pass
        self.proc = self.comandos = self.eventos = None

    def shutdown(self) -> None:
        if self.proc is not None and self.proc.is_alive() and self.comandos is not None:
            try:
                self.comandos.put({"cmd": "stop"}); self.proc.join(timeout=2)
            except Exception:
                pass
        self._reset()

    def diarize(
        self, ruta: str, *, num_speakers: int = -1, threshold: float = 0.5,
        speech_regions: Optional[Sequence[Sequence[float]]] = None,
        adaptive: bool = False, diar_profile: str = "Equilibrada",
        log: Optional[Callable[[str], None]] = None,
        progreso: Optional[Callable[[float], None]] = None,
        cancelado: Optional[Callable[[], bool]] = None,
        time_budget_seconds: Optional[float] = None,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        log = log or (lambda _: None); progreso = progreso or (lambda _: None)
        cancelado = cancelado or (lambda: False)
        self._start(); self.counter += 1
        job_id = f"job-{self.counter}"
        regiones = None
        if speech_regions:
            regiones = [(float(r[0]), float(r[1])) for r in speech_regions if len(r) >= 2]
        self.comandos.put({
            "cmd": "diarize", "job_id": job_id, "ruta": str(ruta),
            "num_speakers": int(num_speakers), "threshold": float(threshold),
            "speech_regions": regiones, "adaptive": bool(adaptive),
            "diar_profile": str(diar_profile),
            "time_budget_seconds": (
                None if time_budget_seconds is None else max(0.0, float(time_budget_seconds))
            ),
        })
        while True:
            if cancelado():
                self._reset(); raise DiarizacionCancelada()
            try:
                jid, tipo, valor = self.eventos.get(timeout=0.20)
            except queue.Empty:
                if self.proc is None or not self.proc.is_alive():
                    code = None if self.proc is None else self.proc.exitcode
                    self._reset()
                    raise RuntimeError(f"El worker persistente de diarización terminó inesperadamente ({code}).")
                continue
            if jid != job_id:
                continue
            if tipo == "log": log(str(valor))
            elif tipo == "progress": progreso(float(valor))
            elif tipo == "result":
                data = dict(valor or {})
                return list(data.get("turns") or []), dict(data.get("meta") or {})
            elif tipo == "error":
                raise RuntimeError("Falló la identificación de hablantes:\n" + str(valor))
