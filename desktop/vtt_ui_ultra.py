#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""UI especializada de la rama Windows Ultra."""
from __future__ import annotations

import vtt_ui_v52 as v52
from vtt_ultra_config import ULTRA_DIAR_PROFILE, ULTRA_PROFILE_NAME


class DiarizacionUltraUIMixin(v52.DiarizacionV52UIMixin):
    def _ui(self):
        super()._ui()
        try:
            self.root.title("VtT Ultra Windows — transcripción rápida con hablantes")
        except Exception:
            pass
        self._force_ultra_default()

    def _aplicar_config(self):
        # La rama es un producto separado: arranca siempre en Ultra, aunque una
        # configuración histórica de VtT estable exista en el mismo directorio.
        super()._aplicar_config()
        self._force_ultra_default()

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
                text="shift 0.35 · máxima velocidad · menor resolución temporal"
            )

    def _update_global_label(self):
        super()._update_global_label()
        if not hasattr(self, "lbl_global_profile"):
            return
        if self.v_global_profile.get() == ULTRA_PROFILE_NAME:
            self.lbl_global_profile.configure(
                text=(
                    "tiny · ASR Rápido · hablantes Auto · diar. Ultrarrápida · "
                    "1 pasada · recomendado en esta rama"
                )
            )

    def _actualizar_resumen_config(self):
        super()._actualizar_resumen_config()
        if not hasattr(self, "lbl_config_main"):
            return
        if self.v_global_profile.get() == ULTRA_PROFILE_NAME:
            self.lbl_config_main.configure(
                text=(
                    "ULTRA WINDOWS · tiny · ASR Rápido · "
                    "Diarización Ultrarrápida / Auto · 1 pasada · "
                    "tiempos por segmento"
                )
            )
