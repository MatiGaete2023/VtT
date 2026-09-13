#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Entry point de VtT Ultra Windows."""
import multiprocessing as mp
import tkinter as tk

from vtt_ultra_config import install_ultra_mode

# Debe instalarse antes de importar UI/performance para que los Combobox vean
# el preset y el perfil de diarización ultrarrápidos.
install_ultra_mode()

import vtt_app as ui
from vtt_pipeline_ultra import PipelineUltraMixin
from vtt_ui_ultra import DiarizacionUltraUIMixin


class VtTApp(DiarizacionUltraUIMixin, PipelineUltraMixin, ui.VtTApp):
    pass


def main():
    try:
        from tkinterdnd2 import TkinterDnD
        root = TkinterDnD.Tk()
        dnd = True
    except Exception:
        root = tk.Tk(); dnd = False
    VtTApp(root, dnd)
    root.mainloop()


if __name__ == "__main__":
    mp.freeze_support()
    main()
