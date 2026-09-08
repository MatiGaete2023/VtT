#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Entry point final de escritorio VtT."""
import multiprocessing as mp
import tkinter as tk

import vtt_app as ui
from vtt_pipeline import PipelineV3Mixin


class VtTApp(PipelineV3Mixin, ui.VtTApp):
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
