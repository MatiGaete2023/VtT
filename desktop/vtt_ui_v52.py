#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""UI V5.2: modos globales orientados al tiempo total."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import transcriptor_whisper as base
import vtt_performance as perf
import vtt_ui_v51 as v51


class DiarizacionV52UIMixin(v51.DiarizacionV51UIMixin):
    def _ui(self):
        self.v_global_profile = tk.StringVar(value="Equilibrado")
        self._global_profile_run = "Equilibrado"
        self._global_applying = False
        super()._ui()
        fr = self.cmb_m.master
        # Modo global antes de los controles individuales.
        for child in fr.grid_slaves():
            info = child.grid_info()
            try:
                row = int(info.get("row", 0))
            except (TypeError, ValueError):
                continue
            if row >= 5:
                child.grid_configure(row=row + 1)
        ttk.Label(fr, text="Modo global:").grid(
            row=5, column=0, sticky="w", padx=4, pady=(6, 4)
        )
        self.cmb_global_profile = ttk.Combobox(
            fr, textvariable=self.v_global_profile,
            values=list(perf.GLOBAL_PROFILES), state="readonly", width=16,
        )
        self.cmb_global_profile.grid(row=5, column=1, sticky="w", padx=4, pady=(6, 4))
        self.lbl_global_profile = ttk.Label(fr, text="", foreground=self.paleta["muted"])
        self.lbl_global_profile.grid(row=5, column=2, columnspan=2, sticky="w", padx=4, pady=(6, 4))

        self.v_global_profile.trace_add("write", lambda *_: self._apply_global_profile())
        self.v_perfil.trace_add("write", lambda *_: self._component_changed())
        self.v_diar_perfil.trace_add("write", lambda *_: self._component_changed())
        self.cmb_m.bind("<<ComboboxSelected>>", lambda _e: self._component_changed(), add="+")
        self._apply_global_profile()

    def _component_changed(self):
        if getattr(self, "_global_applying", False):
            return
        if hasattr(self, "v_global_profile") and self.v_global_profile.get() != "Personalizado":
            self._global_applying = True
            try:
                self.v_global_profile.set("Personalizado")
            finally:
                self._global_applying = False
            self._update_global_label()
            self._actualizar_resumen_config()

    def _apply_global_profile(self):
        if not hasattr(self, "v_global_profile"):
            return
        name = self.v_global_profile.get()
        cfg = perf.global_profile(name)
        self._global_applying = True
        try:
            if cfg["name"] != name:
                self.v_global_profile.set(cfg["name"])
            if cfg.get("model"):
                self.cmb_m.set(str(cfg["model"]))
            if cfg.get("asr_profile"):
                self.v_perfil.set(str(cfg["asr_profile"]))
            if cfg.get("diar_profile"):
                self.v_diar_perfil.set(str(cfg["diar_profile"]))
        finally:
            self._global_applying = False
        self._update_global_label()
        self._actualizar_resumen_config()

    def _update_global_label(self):
        if not hasattr(self, "lbl_global_profile"):
            return
        cfg = perf.global_profile(self.v_global_profile.get())
        if cfg["name"] == "Personalizado":
            text = "controles individuales"
        else:
            text = (
                f"{cfg['model']} · ASR {cfg['asr_profile']} · diar. {cfg['diar_profile']}"
                + (" · recomendado" if cfg["name"] == "Equilibrado" else "")
            )
        self.lbl_global_profile.configure(text=text)

    def _aplicar_config(self):
        # Primero deja que las capas previas restauren exactamente los controles
        # que el usuario ya tenía guardados.
        super()._aplicar_config()

        stored = self.cfg.get("global_profile")
        if stored in perf.GLOBAL_PROFILES:
            value = str(stored)
        else:
            # Migración V5.1 -> V5.2: reconocer un preset solo cuando los tres
            # controles restaurados coinciden. Cualquier combinación distinta
            # queda en Personalizado y NO se modifica silenciosamente.
            value = perf.infer_global_profile(
                self.cmb_m.get(), self.v_perfil.get(), self.v_diar_perfil.get()
            )

        self._global_applying = True
        try:
            self.v_global_profile.set(value)
        finally:
            self._global_applying = False
        # Si existe un preset explícito sí corresponde normalizar sus tres
        # controles; Personalizado conserva lo que restauró super().
        self._apply_global_profile()
        self._global_profile_run = self.v_global_profile.get()

    def _snapshot_config(self):
        super()._snapshot_config()
        c = base.cargar_config()
        c["global_profile"] = self.v_global_profile.get()
        base.guardar_config(c)

    def _iniciar(self):
        self._apply_global_profile()
        self._global_profile_run = self.v_global_profile.get()
        return super()._iniciar()

    def _actualizar_resumen_config(self):
        if not hasattr(self, "lbl_config_main"):
            return
        mode = self.v_global_profile.get() if hasattr(self, "v_global_profile") else "Personalizado"
        if self.v_diarizar.get():
            smode = self.v_num_speakers.get()
            diar = f"{self.v_diar_perfil.get()} / {'Auto' if smode == 'Auto' else smode}"
        else:
            diar = "No"
        gpu = "automática" if self.v_gpu_auto.get() else "CPU"
        self.lbl_config_main.configure(
            text=(
                f"Modo {mode} · {self.cmb_m.get()} · ASR {self.v_perfil.get()} · "
                f"Diarización {diar} · Word {'Sí' if self.v_docx.get() else 'No'} · GPU {gpu}"
            )
        )
