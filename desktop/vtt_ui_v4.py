#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""UI V4 para perfil independiente de diarización."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import transcriptor_whisper as base
import vtt_diarization_v4 as diar4


class DiarizacionV4UIMixin:
    def _ui(self):
        self.v_diar_perfil = tk.StringVar(value="Equilibrada")
        self._diar_profile_run = "Equilibrada"
        super()._ui()

        fr_o = self.cmb_m.master
        # Insertar una fila sin pisar Glosario ni el resumen ya existentes.
        for child in fr_o.grid_slaves():
            info = child.grid_info()
            try:
                row = int(info.get("row", 0))
            except (TypeError, ValueError):
                continue
            if row >= 7:
                child.grid_configure(row=row + 1)

        ttk.Label(fr_o, text="Perfil diarización:").grid(
            row=7, column=0, sticky="w", padx=4, pady=4
        )
        self.cmb_diar_perfil = ttk.Combobox(
            fr_o,
            textvariable=self.v_diar_perfil,
            values=list(diar4.DIARIZATION_PROFILES),
            state="readonly",
            width=16,
        )
        self.cmb_diar_perfil.grid(
            row=7, column=1, sticky="w", padx=4, pady=4
        )
        self.lbl_diar_perfil = ttk.Label(
            fr_o, text="", foreground=self.paleta["muted"]
        )
        self.lbl_diar_perfil.grid(
            row=7, column=2, columnspan=2, sticky="w", padx=4, pady=4
        )

        self.v_diar_perfil.trace_add(
            "write", lambda *_: self._cambio_perfil_diarizacion()
        )
        self._cambio_perfil_diarizacion()

    def _aplicar_config(self):
        super()._aplicar_config()
        valor = str(self.cfg.get("diarization_profile", "Equilibrada"))
        if valor in diar4.DIARIZATION_PROFILES:
            self.v_diar_perfil.set(valor)
        else:
            self.v_diar_perfil.set("Equilibrada")
        self._diar_profile_run = self.v_diar_perfil.get()
        self._cambio_perfil_diarizacion()

    def _snapshot_config(self):
        super()._snapshot_config()
        c = base.cargar_config()
        c["diarization_profile"] = self.v_diar_perfil.get()
        base.guardar_config(c)

    def _iniciar(self):
        # Snapshot plano antes de lanzar el hilo: no leemos StringVar desde
        # el worker.
        self._diar_profile_run = self.v_diar_perfil.get()
        return super()._iniciar()

    def _cambio_perfil_diarizacion(self):
        if not hasattr(self, "lbl_diar_perfil"):
            self._actualizar_resumen_config()
            return
        nombre, cfg = diar4.perfil_diarizacion(self.v_diar_perfil.get())
        if nombre != self.v_diar_perfil.get():
            self.v_diar_perfil.set(nombre)
        self.lbl_diar_perfil.configure(
            text=f"shift {float(cfg['window_shift_ratio']):.2f}"
        )
        self._actualizar_resumen_config()

    def _actualizar_resumen_config(self):
        if not hasattr(self, "lbl_config_main"):
            return
        if self.v_diarizar.get():
            modo = self.v_num_speakers.get()
            hablantes = "Auto estructural" if modo == "Auto" else str(modo)
            diar = f"{self.v_diar_perfil.get()} / {hablantes}"
        else:
            diar = "No"
        gpu = "automática" if self.v_gpu_auto.get() else "CPU"
        self.lbl_config_main.configure(
            text=(
                f"Configuración actual: {self.cmb_m.get()} · ASR {self.v_perfil.get()} · "
                f"Diarización: {diar} · Word: {'Sí' if self.v_docx.get() else 'No'} · "
                f"GPU: {gpu}"
            )
        )
