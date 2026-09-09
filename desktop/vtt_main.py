#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Entry point final de escritorio VtT V5.2-performance."""
import multiprocessing as mp
import tkinter as tk

import vtt_app as ui
from vtt_pipeline_v52 import PipelineV52Mixin
from vtt_ui_v52 import DiarizacionV52UIMixin


class VtTApp(DiarizacionV52UIMixin, PipelineV52Mixin, ui.VtTApp):
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
