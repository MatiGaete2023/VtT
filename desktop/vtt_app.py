#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Interfaz final de escritorio VtT.

Añade sobre VtTEnhancedApp:
- diarización aislada en otro proceso para mantener Tkinter responsivo;
- porcentaje y ETA de identificación de hablantes;
- controles principales visibles para perfil/Word/hablantes;
- tamaño ajustable y persistente del registro.
"""
from __future__ import annotations

import multiprocessing as mp
import queue
import time
from pathlib import Path

import tkinter as tk
from tkinter import ttk

import transcriptor_whisper as base
import vtt_core as core
import vtt_enhanced as enhanced
import vtt_diarization_process as dproc


class VtTApp(enhanced.VtTEnhancedApp):
    def _ui(self):
        self._cola_diar_ui = queue.Queue()
        self._altura_log = 8
        super()._ui()

        fr_o = self.cmb_m.master

        ttk.Label(fr_o, text="Perfil:").grid(
            row=5, column=0, sticky="w", padx=4, pady=(6, 4)
        )
        self.cmb_perfil_main = ttk.Combobox(
            fr_o,
            textvariable=self.v_perfil,
            values=list(core.PERFILES),
            state="readonly",
            width=16,
        )
        self.cmb_perfil_main.grid(row=5, column=1, sticky="w", padx=4, pady=(6, 4))
        ttk.Checkbutton(
            fr_o, text="Word (.docx)", variable=self.v_docx
        ).grid(row=5, column=2, sticky="w", padx=4, pady=(6, 4))

        ttk.Label(fr_o, text="Hablantes:").grid(
            row=6, column=0, sticky="w", padx=4, pady=4
        )
        ttk.Checkbutton(
            fr_o,
            text="Identificar (Persona 1, Persona 2…)",
            variable=self.v_diarizar,
        ).grid(row=6, column=1, columnspan=2, sticky="w", padx=4, pady=4)
        fr_num = ttk.Frame(fr_o)
        fr_num.grid(row=6, column=3, sticky="w", padx=4, pady=4)
        ttk.Label(fr_num, text="N.º:").pack(side="left")
        self.cmb_speakers_main = ttk.Combobox(
            fr_num,
            textvariable=self.v_num_speakers,
            values=["Auto", "2", "3", "4", "5", "6", "7", "8"],
            state="readonly",
            width=7,
        )
        self.cmb_speakers_main.pack(side="left", padx=(4, 0))

        ttk.Label(fr_o, text="Glosario / nombres:").grid(
            row=7, column=0, sticky="w", padx=4, pady=4
        )
        ttk.Entry(fr_o, textvariable=self.v_glosario).grid(
            row=7, column=1, columnspan=3, sticky="we", padx=4, pady=4
        )

        self.lbl_config_main = ttk.Label(
            fr_o, text="", foreground=self.paleta["muted"]
        )
        self.lbl_config_main.grid(
            row=8, column=0, columnspan=4, sticky="w", padx=4, pady=(2, 4)
        )

        fr_l = self.log.master
        self.log.pack_forget()
        self.fr_tamano_registro = ttk.Frame(fr_l)
        self.fr_tamano_registro.pack(fill="x", pady=(0, 4))
        ttk.Label(
            self.fr_tamano_registro,
            text="Tamaño del registro:",
            style="Subtitle.TLabel",
        ).pack(side="left")
        ttk.Button(
            self.fr_tamano_registro, text="−", width=3,
            command=lambda: self._ajustar_registro(-2)
        ).pack(side="left", padx=(8, 2))
        ttk.Button(
            self.fr_tamano_registro, text="+", width=3,
            command=lambda: self._ajustar_registro(2)
        ).pack(side="left", padx=2)
        ttk.Label(
            self.fr_tamano_registro,
            text="(también Ctrl+− / Ctrl++)",
            style="Subtitle.TLabel",
        ).pack(side="left", padx=(8, 0))
        self.log.pack(fill="both", expand=True)

        self.root.bind("<Control-plus>", lambda _e: self._ajustar_registro(2))
        self.root.bind("<Control-equal>", lambda _e: self._ajustar_registro(2))
        self.root.bind("<Control-minus>", lambda _e: self._ajustar_registro(-2))

        for variable in (
            self.v_perfil, self.v_docx, self.v_diarizar,
            self.v_num_speakers, self.v_gpu_auto,
        ):
            variable.trace_add("write", lambda *_: self._actualizar_resumen_config())
        self.cmb_m.bind(
            "<<ComboboxSelected>>",
            lambda _e: self._actualizar_resumen_config(),
            add="+",
        )
        self.cmb_i.bind(
            "<<ComboboxSelected>>",
            lambda _e: self._actualizar_resumen_config(),
            add="+",
        )

        self.root.geometry("1000x900")
        self.root.minsize(760, 720)
        self.root.after(120, self._procesar_cola_diarizacion)
        self._actualizar_resumen_config()

    def _aplicar_config(self):
        super()._aplicar_config()
        try:
            altura = int(self.cfg.get("registro_altura", 8))
        except (TypeError, ValueError):
            altura = 8
        self._altura_log = max(3, min(30, altura))
        self.log.configure(height=self._altura_log)
        self._actualizar_resumen_config()

    def _snapshot_config(self):
        super()._snapshot_config()
        c = base.cargar_config()
        c["registro_altura"] = int(getattr(self, "_altura_log", 8))
        base.guardar_config(c)

    def _ajustar_registro(self, delta: int):
        actual = int(getattr(self, "_altura_log", self.log.cget("height")))
        nuevo = max(3, min(30, actual + int(delta)))
        if nuevo == actual:
            return
        self._altura_log = nuevo
        self.log.configure(height=nuevo)
        self.root.update_idletasks()
        self._snapshot_config()

    def _actualizar_resumen_config(self):
        if not hasattr(self, "lbl_config_main"):
            return
        hablantes = (
            f"Sí ({self.v_num_speakers.get()})"
            if self.v_diarizar.get()
            else "No"
        )
        gpu = "automática" if self.v_gpu_auto.get() else "CPU"
        self.lbl_config_main.configure(
            text=(
                f"Configuración actual: {self.cmb_m.get()} · "
                f"{self.v_perfil.get()} · Hablantes: {hablantes} · "
                f"Word: {'Sí' if self.v_docx.get() else 'No'} · GPU: {gpu}"
            )
        )

    def _emitir_progreso_diarizacion(
        self, porcentaje: float, inicio: float, nombre: str
    ) -> None:
        pct = max(0.0, min(100.0, float(porcentaje)))
        restante = dproc.estimar_restante(pct, time.monotonic() - inicio)
        self._cola_diar_ui.put((pct, restante, nombre))

    def _procesar_cola_diarizacion(self):
        try:
            ultimo = None
            while True:
                ultimo = self._cola_diar_ui.get_nowait()
        except queue.Empty:
            pass

        if ultimo is not None:
            pct, restante, nombre = ultimo
            self.pb["value"] = pct
            if pct <= 0:
                texto = (
                    f"Identificando hablantes: {Path(nombre).name} · "
                    "0% · preparando audio/modelos…"
                )
            else:
                eta = (
                    f" · tiempo restante ~{base.ts_simple(restante)}"
                    if restante is not None
                    else ""
                )
                texto = (
                    f"Identificando hablantes: {Path(nombre).name} · "
                    f"{pct:.0f}%{eta}"
                )
            self._set_estado(texto, "grabando")

        try:
            self.root.after(120, self._procesar_cola_diarizacion)
        except tk.TclError:
            pass

    def _worker_vtt(self, *args, **kwargs):
        original = enhanced.diar.diarizar

        def diarizar_sin_bloquear(
            ruta,
            carpeta_modelos,
            num_speakers=-1,
            threshold=0.5,
            log=None,
            progreso=None,
        ):
            inicio = time.monotonic()
            nombre = Path(ruta).name
            self._cola_diar_ui.put((0.0, None, nombre))

            def avance(pct: float):
                if progreso is not None:
                    progreso(pct)
                self._emitir_progreso_diarizacion(pct, inicio, nombre)

            try:
                return dproc.diarizar_responsivo(
                    ruta,
                    carpeta_modelos,
                    num_speakers=num_speakers,
                    threshold=threshold,
                    log=log,
                    progreso=avance,
                    cancelado=self.cancelar.is_set,
                )
            except dproc.DiarizacionCancelada:
                raise base.Cancelado()

        enhanced.diar.diarizar = diarizar_sin_bloquear
        try:
            return super()._worker_vtt(*args, **kwargs)
        finally:
            enhanced.diar.diarizar = original


def main():
    try:
        from tkinterdnd2 import TkinterDnD
        root = TkinterDnD.Tk()
        dnd = True
    except Exception:
        root = tk.Tk()
        dnd = False
    VtTApp(root, dnd)
    root.mainloop()


if __name__ == "__main__":
    mp.freeze_support()
    main()
