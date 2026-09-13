#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""UI especializada de la rama Windows Ultra."""
from __future__ import annotations

import vtt_ui_v52 as v52
from vtt_ultra_config import (
    ULTRA_DIAR_PROFILE,
    ULTRA_PROFILE_NAME,
    ULTRA_QUALITY_PROFILE_NAME,
)

_ULTRA_MODES = {ULTRA_PROFILE_NAME, ULTRA_QUALITY_PROFILE_NAME}


class DiarizacionUltraUIMixin(v52.DiarizacionV52UIMixin):
    def _ui(self):
        super()._ui()
        try:
            self.root.title("VtT Ultra Windows — velocidad o calidad 90s")
        except Exception:
            pass
        if hasattr(self, "cmb_global_profile"):
            self.cmb_global_profile.configure(width=21)
        self._force_ultra_default()

    def _aplicar_config(self):
        # Conserva la variante Ultra elegida en la sesión anterior. Una
        # configuración de la rama estable (Equilibrado/Preciso/etc.) se migra
        # a Ultra Máxima para evitar ejecutar accidentalmente otro producto.
        super()._aplicar_config()
        current = self.v_global_profile.get() if hasattr(self, "v_global_profile") else ""
        if current not in _ULTRA_MODES:
            self._force_ultra_default()
        else:
            self._global_profile_run = current
            self._apply_global_profile()

    def _force_ultra_default(self):
        if not hasattr(self, "v_global_profile"):
            return
        self._global_applying = True
        try:
            self.v_global_profile.set(ULTRA_PROFILE_NAME)
        finally:
            self._global_applying = False
        self._apply_global_profile()
        self._global_profile_run = ULTRA_PROFILE_NAME

    def _cambio_perfil_diarizacion(self):
        super()._cambio_perfil_diarizacion()
        if not hasattr(self, "lbl_diar_perfil"):
            return
        if self.v_diar_perfil.get() == ULTRA_DIAR_PROFILE:
            self.lbl_diar_perfil.configure(
                text="shift 0.35 · 1 pasada · perfil común de ambas variantes Ultra"
            )

    def _update_global_label(self):
        super()._update_global_label()
        if not hasattr(self, "lbl_global_profile"):
            return
        mode = self.v_global_profile.get()
        if mode == ULTRA_PROFILE_NAME:
            self.lbl_global_profile.configure(
                text="tiny · ASR Rápido · Auto · 1 pasada · máxima velocidad"
            )
        elif mode == ULTRA_QUALITY_PROFILE_NAME:
            self.lbl_global_profile.configure(
                text="base · ASR Rápido · Auto · 1 pasada · palabras + identidad ligera"
            )

    def _actualizar_resumen_config(self):
        super()._actualizar_resumen_config()
        if not hasattr(self, "lbl_config_main"):
            return
        mode = self.v_global_profile.get()
        if mode == ULTRA_PROFILE_NAME:
            self.lbl_config_main.configure(
                text=(
                    "ULTRA MÁXIMA · tiny · ASR Rápido · "
                    "Diarización Ultrarrápida / Auto · 1 pasada · "
                    "alineación por segmento"
                )
            )
        elif mode == ULTRA_QUALITY_PROFILE_NAME:
            self.lbl_config_main.configure(
                text=(
                    "ULTRA CALIDAD 90s · base · ASR Rápido · "
                    "Diarización Ultrarrápida / Auto · 1 pasada · "
                    "alineación por palabra + identidad ligera"
                )
            )
