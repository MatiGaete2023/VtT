#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Entry point final de escritorio VtT."""
import multiprocessing as mp
import tkinter as tk

import vtt_app as ui
from vtt_pipeline_v4 import PipelineV4Mixin
from vtt_ui_v4 import DiarizacionV4UIMixin


class VtTApp(DiarizacionV4UIMixin, PipelineV4Mixin, ui.VtTApp):
    pass


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
