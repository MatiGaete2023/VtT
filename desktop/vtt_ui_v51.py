#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""UI V5.1: recomendaciones explícitas de costo de diarización."""
from __future__ import annotations

import vtt_ui_v4 as v4


class DiarizacionV51UIMixin(v4.DiarizacionV4UIMixin):
    def _cambio_perfil_diarizacion(self):
        super()._cambio_perfil_diarizacion()
        if not hasattr(self, "lbl_diar_perfil"):
            return
        nombre = self.v_diar_perfil.get()
        if nombre == "Equilibrada":
            self.lbl_diar_perfil.configure(text="shift 0.20 · recomendada")
        elif nombre == "Precisa":
            self.lbl_diar_perfil.configure(text="shift 0.10 · alto costo CPU")
        else:
            self.lbl_diar_perfil.configure(text="shift 0.25 · prioriza velocidad")
