#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Interfaz final de escritorio VtT.

Añade sobre VtTEnhancedApp:
- diarización aislada en otro proceso para mantener Tkinter responsivo;
- porcentaje y ETA de identificación de hablantes;
- controles principales visibles para perfil/Word/hablantes;
- tamaño ajustable y persistente del registro;
- modo compacto para pantallas de baja altura;
- auto-diarización conservadora y hablantes consecutivos;
- perfil Preciso batcheado para reducir tiempos en CPU.
"""
from __future__ import annotations

import multiprocessing as mp
import queue
import time
from pathlib import Path

import tkinter as tk
from tkinter import ttk

import transcriptor_whisper as base
import vtt_core as core
import vtt_enhanced as enhanced
import vtt_diarization_process as dproc
import vtt_tuning as tuning


# "Preciso" antes usaba la ruta secuencial y en la prueba real fue mas lento
# que tiempo real. Se conserva beam=5, pero se procesa en lotes moderados para
# no disparar el consumo de RAM tanto como batch_size=8.
core.PERFILES["Preciso"].update({
    "batched": True,
    "batch_size": 4,
    "beam_size": 5,
    "descripcion": "Mayor precisión con batching moderado; conserva beam 5.",
})


class VtTApp(enhanced.VtTEnhancedApp):
    def _ui(self):
        self._cola_diar_ui = queue.Queue()
        self._altura_log = 6
        self._fuentes_expandidas = False
        super()._ui()

        fr_o = self.cmb_m.master

        ttk.Label(fr_o, text="Perfil:").grid(
            row=5, column=0, sticky="w", padx=4, pady=(6, 4)
        )
        self.cmb_perfil_main = ttk.Combobox(
            fr_o,
            textvariable=self.v_perfil,
            values=list(core.PERFILES),
            state="readonly",
            width=16,
        )
        self.cmb_perfil_main.grid(row=5, column=1, sticky="w", padx=4, pady=(6, 4))
        ttk.Checkbutton(
            fr_o, text="Word (.docx)", variable=self.v_docx
        ).grid(row=5, column=2, sticky="w", padx=4, pady=(6, 4))

        ttk.Label(fr_o, text="Hablantes:").grid(
            row=6, column=0, sticky="w", padx=4, pady=4
        )
        ttk.Checkbutton(
            fr_o,
            text="Identificar (Persona 1, Persona 2…)",
            variable=self.v_diarizar,
        ).grid(row=6, column=1, columnspan=2, sticky="w", padx=4, pady=4)
        fr_num = ttk.Frame(fr_o)
        fr_num.grid(row=6, column=3, sticky="w", padx=4, pady=4)
        ttk.Label(fr_num, text="N.º:").pack(side="left")
        self.cmb_speakers_main = ttk.Combobox(
            fr_num,
            textvariable=self.v_num_speakers,
            values=["Auto", "2", "3", "4", "5", "6", "7", "8"],
            state="readonly",
            width=7,
        )
        self.cmb_speakers_main.pack(side="left", padx=(4, 0))

        ttk.Label(fr_o, text="Glosario / nombres:").grid(
            row=7, column=0, sticky="w", padx=4, pady=4
        )
        ttk.Entry(fr_o, textvariable=self.v_glosario).grid(
            row=7, column=1, columnspan=3, sticky="we", padx=4, pady=4
        )

        self.lbl_config_main = ttk.Label(
            fr_o, text="", foreground=self.paleta["muted"]
        )
        self.lbl_config_main.grid(
            row=8, column=0, columnspan=4, sticky="w", padx=4, pady=(2, 4)
        )

        fr_l = self.log.master
        self.log.pack_forget()
        self.fr_tamano_registro = ttk.Frame(fr_l)
        self.fr_tamano_registro.pack(fill="x", pady=(0, 4))
        ttk.Label(
            self.fr_tamano_registro,
            text="Tamaño del registro:",
            style="Subtitle.TLabel",
        ).pack(side="left")
        ttk.Button(
            self.fr_tamano_registro, text="−", width=3,
            command=lambda: self._ajustar_registro(-2)
        ).pack(side="left", padx=(8, 2))
        ttk.Button(
            self.fr_tamano_registro, text="+", width=3,
            command=lambda: self._ajustar_registro(2)
        ).pack(side="left", padx=2)
        ttk.Label(
            self.fr_tamano_registro,
            text="(también Ctrl+− / Ctrl++)",
            style="Subtitle.TLabel",
        ).pack(side="left", padx=(8, 0))
        self.log.pack(fill="both", expand=True)

        self.root.bind("<Control-plus>", lambda _e: self._ajustar_registro(2))
        self.root.bind("<Control-equal>", lambda _e: self._ajustar_registro(2))
        self.root.bind("<Control-minus>", lambda _e: self._ajustar_registro(-2))

        for variable in (
            self.v_perfil, self.v_docx, self.v_diarizar,
            self.v_num_speakers, self.v_gpu_auto,
        ):
            variable.trace_add("write", lambda *_: self._actualizar_resumen_config())
        self.cmb_m.bind(
            "<<ComboboxSelected>>",
            lambda _e: self._actualizar_resumen_config(),
            add="+",
        )
        self.cmb_i.bind(
            "<<ComboboxSelected>>",
            lambda _e: self._actualizar_resumen_config(),
            add="+",
        )

        # Las tres secciones menos usadas consumían ~200 px verticales. Se
        # conservan completas, pero plegadas bajo un único control.
        self._fr_files = self.lst.master
        self._fr_fuentes = [self.lbl_ff.master, self.btn_yt.master, self.cmb_dev.master]
        cont = self._fr_files.master
        for frame in self._fr_fuentes:
            frame.pack_forget()
        self.fr_fuentes_toggle = ttk.Frame(cont)
        self.fr_fuentes_toggle.pack(
            fill="x", padx=8, pady=(2, 4), before=self._fr_files
        )
        self.btn_fuentes = ttk.Button(
            self.fr_fuentes_toggle,
            text="▸ Mostrar YouTube, grabación y FFmpeg",
            command=self._alternar_fuentes,
        )
        self.btn_fuentes.pack(side="left")
        ttk.Label(
            self.fr_fuentes_toggle,
            text="(plegado para ahorrar espacio)",
            style="Subtitle.TLabel",
        ).pack(side="left", padx=(8, 0))

        # Reducir el alto base de la lista ayuda en 1366x768 / 1600x900 sin
        # perder la posibilidad de redimensionar la ventana.
        self.lst.configure(height=4)

        ancho_pantalla = max(800, int(self.root.winfo_screenwidth()))
        alto_pantalla = max(650, int(self.root.winfo_screenheight()))
        ancho = max(760, min(1000, ancho_pantalla - 80))
        alto = max(620, min(800, alto_pantalla - 100))
        self.root.geometry(f"{ancho}x{alto}")
        self.root.minsize(720, 560)

        self.root.after(120, self._procesar_cola_diarizacion)
        self._actualizar_resumen_config()

    def _aplicar_config(self):
        super()._aplicar_config()
        try:
            altura = int(self.cfg.get("registro_altura", 6))
        except (TypeError, ValueError):
            altura = 6
        # En pantallas de 900 px o menos evitamos que un valor antiguo deje
        # fuera de vista los botones inferiores; el usuario puede ampliarlo.
        if int(self.root.winfo_screenheight()) <= 900:
            altura = min(altura, 6)
        self._altura_log = max(3, min(30, altura))
        self.log.configure(height=self._altura_log)
        if bool(self.cfg.get("fuentes_expandidas", False)):
            self._mostrar_fuentes(True, persistir=False)
        self._actualizar_resumen_config()

    def _snapshot_config(self):
        super()._snapshot_config()
        c = base.cargar_config()
        c["registro_altura"] = int(getattr(self, "_altura_log", 6))
        c["fuentes_expandidas"] = bool(
            getattr(self, "_fuentes_expandidas", False)
        )
        base.guardar_config(c)

    def _ajustar_registro(self, delta: int):
        actual = int(getattr(self, "_altura_log", self.log.cget("height")))
        nuevo = max(3, min(30, actual + int(delta)))
        if nuevo == actual:
            return
        self._altura_log = nuevo
        self.log.configure(height=nuevo)
        self.root.update_idletasks()
        self._snapshot_config()

    def _mostrar_fuentes(self, mostrar: bool, persistir: bool = True):
        mostrar = bool(mostrar)
        if not hasattr(self, "_fr_fuentes"):
            return
        if mostrar:
            for frame in self._fr_fuentes:
                if not frame.winfo_manager():
                    frame.pack(
                        fill="x", padx=8, pady=4, before=self._fr_files
                    )
            self.btn_fuentes.configure(
                text="▾ Ocultar YouTube, grabación y FFmpeg"
            )
        else:
            for frame in self._fr_fuentes:
                frame.pack_forget()
            self.btn_fuentes.configure(
                text="▸ Mostrar YouTube, grabación y FFmpeg"
            )
        self._fuentes_expandidas = mostrar
        if persistir:
            self._snapshot_config()

    def _alternar_fuentes(self):
        self._mostrar_fuentes(not self._fuentes_expandidas)

    def _actualizar_resumen_config(self):
        if not hasattr(self, "lbl_config_main"):
            return
        if self.v_diarizar.get():
            modo = self.v_num_speakers.get()
            hablantes = "Sí (Auto conservador)" if modo == "Auto" else f"Sí ({modo})"
        else:
            hablantes = "No"
        gpu = "automática" if self.v_gpu_auto.get() else "CPU"
        self.lbl_config_main.configure(
            text=(
                f"Configuración actual: {self.cmb_m.get()} · "
                f"{self.v_perfil.get()} · Hablantes: {hablantes} · "
                f"Word: {'Sí' if self.v_docx.get() else 'No'} · GPU: {gpu}"
            )
        )

    def _emitir_progreso_diarizacion(
        self, porcentaje: float, inicio: float, nombre: str
    ) -> None:
        pct = max(0.0, min(100.0, float(porcentaje)))
        restante = dproc.estimar_restante(pct, time.monotonic() - inicio)
        self._cola_diar_ui.put((pct, restante, nombre))

    def _procesar_cola_diarizacion(self):
        try:
            ultimo = None
            while True:
                ultimo = self._cola_diar_ui.get_nowait()
        except queue.Empty:
            pass

        if ultimo is not None:
            pct, restante, nombre = ultimo
            self.pb["value"] = pct
            if pct <= 0:
                texto = (
                    f"Identificando hablantes: {Path(nombre).name} · "
                    "0% · preparando audio/modelos…"
                )
            else:
                eta = (
                    f" · tiempo restante ~{base.ts_simple(restante)}"
                    if restante is not None
                    else ""
                )
                texto = (
                    f"Identificando hablantes: {Path(nombre).name} · "
                    f"{pct:.0f}%{eta}"
                )
            self._set_estado(texto, "grabando")

        try:
            self.root.after(120, self._procesar_cola_diarizacion)
        except tk.TclError:
            pass

    def _worker_vtt(self, *args, **kwargs):
        original_diar = enhanced.diar.diarizar
        original_asignar = core.asignar_hablantes

        def asignar_consecutivos(segmentos, turnos):
            asignados, _speakers = original_asignar(segmentos, turnos)
            return tuning.renumerar_hablantes_en_uso(asignados)

        def diarizar_sin_bloquear(
            ruta,
            carpeta_modelos,
            num_speakers=-1,
            threshold=0.5,
            log=None,
            progreso=None,
        ):
            inicio = time.monotonic()
            nombre = Path(ruta).name
            self._cola_diar_ui.put((0.0, None, nombre))

            # Cuando el usuario conoce el número, sherpa-onnx ignora threshold.
            # En Auto usamos un umbral más alto y conservador: el valor anterior
            # 0.50 tiende a crear demasiados clusters en audio de conversación.
            threshold_real = (
                tuning.AUTO_CLUSTER_THRESHOLD
                if int(num_speakers) < 0
                else float(threshold)
            )
            if log is not None:
                if self.t_transcripcion_inicio:
                    asr_seg = max(0.0, time.time() - self.t_transcripcion_inicio)
                    log(
                        "Transcripción ASR completada; "
                        f"tiempo de la etapa ~{base.ts_simple(asr_seg)}."
                    )
                if int(num_speakers) < 0:
                    log(
                        "Auto de hablantes: clustering conservador "
                        f"(umbral {threshold_real:.2f})."
                    )

            def avance(pct: float):
                if progreso is not None:
                    progreso(pct)
                self._emitir_progreso_diarizacion(pct, inicio, nombre)

            try:
                resultado = dproc.diarizar_responsivo(
                    ruta,
                    carpeta_modelos,
                    num_speakers=num_speakers,
                    threshold=threshold_real,
                    log=log,
                    progreso=avance,
                    cancelado=self.cancelar.is_set,
                )
                if log is not None:
                    log(
                        "Identificación de hablantes completada; "
                        f"tiempo de la etapa ~{base.ts_simple(time.monotonic() - inicio)}."
                    )
                return resultado
            except dproc.DiarizacionCancelada:
                raise base.Cancelado()

        enhanced.diar.diarizar = diarizar_sin_bloquear
        core.asignar_hablantes = asignar_consecutivos
        try:
            return enhanced.VtTEnhancedApp._worker_vtt(self, *args, **kwargs)
        finally:
            enhanced.diar.diarizar = original_diar
            core.asignar_hablantes = original_asignar


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
