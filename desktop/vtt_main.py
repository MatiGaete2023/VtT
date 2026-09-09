#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Entry point final de escritorio VtT."""
import multiprocessing as mp
import tkinter as tk

import vtt_app as ui
from vtt_pipeline_v51 import PipelineV51Mixin
from vtt_ui_v51 import DiarizacionV51UIMixin


class VtTApp(DiarizacionV51UIMixin, PipelineV51Mixin, ui.VtTApp):
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
