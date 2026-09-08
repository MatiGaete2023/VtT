#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Capa mejorada de VtT: velocidad, diarización, DOCX y revisión."""
from __future__ import annotations

import os
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

import transcriptor_whisper as base
import vtt_core as core
import vtt_diarization as diar

base.EXTS = core.EXTS_OFICIALES


class VtTEnhancedApp(base.TranscriptorApp):
    def _ui(self):
        self.v_perfil = tk.StringVar(value="Equilibrado")
        self.v_docx = tk.BooleanVar(value=True)
        self.v_diarizar = tk.BooleanVar(value=False)
        self.v_num_speakers = tk.StringVar(value="Auto")
        self.v_gpu_auto = tk.BooleanVar(value=True)
        self.v_glosario = tk.StringVar(value="")
        self.v_max_bloque = tk.DoubleVar(value=35.0)
        self.v_pausa_bloque = tk.DoubleVar(value=1.4)
        self._modelo_backend = None
        self.ultima_revision: Optional[Dict[str, Any]] = None
        super()._ui()
        self.root.title("VtT — Transcriptor local mejorado")
        self.root.geometry("900x800")
        barra = tk.Menu(self.root)
        menu = tk.Menu(barra, tearoff=False)
        menu.add_command(label="Opciones avanzadas…", command=self._opciones)
        menu.add_command(label="Revisar última transcripción…", command=self._revision)
        menu.add_separator()
        menu.add_command(label="Carpeta de modelos de hablantes", command=self._abrir_modelos)
        barra.add_cascade(label="VtT", menu=menu)
        self.root.config(menu=barra)

    def _aplicar_config(self):
        super()._aplicar_config()
        c = self.cfg
        if c.get("perfil") in core.PERFILES:
            self.v_perfil.set(c["perfil"])
        self.v_docx.set(bool(c.get("docx", True)))
        self.v_diarizar.set(bool(c.get("diarizar", False)))
        self.v_num_speakers.set(str(c.get("num_speakers", "Auto")))
        self.v_gpu_auto.set(bool(c.get("gpu_auto", True)))
        self.v_glosario.set(str(c.get("glosario", "")))
        try:
            self.v_max_bloque.set(float(c.get("max_bloque", 35.0)))
            self.v_pausa_bloque.set(float(c.get("pausa_bloque", 1.4)))
        except (TypeError, ValueError):
            pass
        if "json" not in c:
            self.v_json.set(True)

    def _snapshot_config(self):
        super()._snapshot_config()
        c = base.cargar_config()
        c.update({
            "perfil": self.v_perfil.get(), "docx": bool(self.v_docx.get()),
            "diarizar": bool(self.v_diarizar.get()), "num_speakers": self.v_num_speakers.get(),
            "gpu_auto": bool(self.v_gpu_auto.get()), "glosario": self.v_glosario.get(),
            "max_bloque": float(self.v_max_bloque.get()),
            "pausa_bloque": float(self.v_pausa_bloque.get()),
        })
        base.guardar_config(c)

    def _opciones(self):
        w = tk.Toplevel(self.root); w.title("Opciones avanzadas VtT"); w.transient(self.root)
        f = ttk.Frame(w, padding=14); f.pack(fill="both", expand=True)
        ttk.Label(f, text="Perfil:").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Combobox(f, textvariable=self.v_perfil, values=list(core.PERFILES),
                     state="readonly", width=16).grid(row=0, column=1, sticky="w")
        ttk.Checkbutton(f, text="GPU automática si CUDA ya está disponible",
                        variable=self.v_gpu_auto).grid(row=1, column=0, columnspan=3, sticky="w", pady=4)
        ttk.Checkbutton(f, text="Exportar Word (.docx)", variable=self.v_docx).grid(
            row=2, column=0, columnspan=3, sticky="w", pady=4)
        ttk.Checkbutton(f, text="Identificar hablantes (Persona 1, Persona 2…)",
                        variable=self.v_diarizar).grid(row=3, column=0, columnspan=2, sticky="w", pady=4)
        ttk.Label(f, text="N.º:").grid(row=3, column=2, sticky="e")
        ttk.Combobox(f, textvariable=self.v_num_speakers,
                     values=["Auto", "2", "3", "4", "5", "6", "7", "8"],
                     state="readonly", width=7).grid(row=3, column=3, sticky="w")
        ttk.Label(f, text="Glosario / nombres:").grid(row=4, column=0, sticky="w", pady=4)
        ttk.Entry(f, textvariable=self.v_glosario, width=60).grid(row=4, column=1, columnspan=3, sticky="we")
        ttk.Label(f, text="Máximo bloque (s):").grid(row=5, column=0, sticky="w", pady=4)
        ttk.Spinbox(f, from_=15, to=90, increment=5, textvariable=self.v_max_bloque,
                    width=8).grid(row=5, column=1, sticky="w")
        ttk.Label(f, text="Pausa de corte (s):").grid(row=5, column=2, sticky="e")
        ttk.Spinbox(f, from_=0.5, to=5, increment=0.1, textvariable=self.v_pausa_bloque,
                    width=8).grid(row=5, column=3, sticky="w")
        ttk.Label(f, text="SRT/VTT mantienen segmentos finos; TXT/MD/DOCX usan bloques legibles.").grid(
            row=6, column=0, columnspan=4, sticky="w", pady=(8, 4))
        def guardar():
            self._snapshot_config(); w.destroy()
        ttk.Button(f, text="Guardar", command=guardar, style="Accent.TButton").grid(
            row=7, column=3, sticky="e", pady=(8, 0))
        w.protocol("WM_DELETE_WINDOW", guardar)

    def _abrir_modelos(self):
        p = base.CARPETA_DATOS / "modelos_hablantes"; p.mkdir(parents=True, exist_ok=True)
        if not base.abrir_en_explorador(p):
            messagebox.showinfo("Modelos de hablantes", str(p))

    def _insertar_archivo(self, ruta):
        if ruta in self.archivos or not os.path.isfile(ruta):
            return
        ok, detalle = core.probar_pista_audio(ruta)
        if not ok:
            self._escribe(f"Archivo rechazado: {Path(ruta).name} — {detalle}")
            messagebox.showerror("Archivo no compatible", f"{Path(ruta).name}\n\n{detalle}")
            return
        self.archivos.append(ruta); self.lst.insert("end", ruta)
        self._escribe(f"Archivo válido: {Path(ruta).name} · {detalle}")

    def _backend(self):
        if self.v_gpu_auto.get():
            try:
                import ctranslate2
                if int(ctranslate2.get_cuda_device_count()) > 0:
                    return "cuda", "float16"
            except Exception:
                pass
        return "cpu", "int8"

    def _iniciar(self):
        if self.transcribiendo:
            return
        if not self.archivos:
            messagebox.showwarning("Sin archivos", "Agrega al menos un audio o video."); return
        formatos = {
            "txt": self.v_txt.get(), "md": self.v_md.get(), "srt": self.v_srt.get(),
            "vtt": self.v_vtt.get(), "json": self.v_json.get(), "docx": self.v_docx.get(),
        }
        if not any(formatos.values()):
            messagebox.showwarning("Formato", "Marca al menos un formato de salida."); return
        salida = self.v_out.get().strip() or None
        if salida and not os.path.isdir(salida):
            messagebox.showerror("Salida", "La carpeta de salida no existe."); return
        self._snapshot_config()
        idioma = base.IDIOMAS[self.cmb_i.get()]; modelo = self.cmb_m.get()
        opts = {
            "perfil": self.v_perfil.get(), "diarizar": bool(self.v_diarizar.get()),
            "num_speakers": self.v_num_speakers.get(), "glosario": self.v_glosario.get(),
            "max_bloque": float(self.v_max_bloque.get()), "pausa_bloque": float(self.v_pausa_bloque.get()),
        }
        self.transcribiendo = True; self.cancelar.clear(); self.btn_run.config(state="disabled")
        self.btn_cancel.config(state="normal"); self.btn_open.config(state="disabled"); self.pb["value"] = 0
        self.estado_actual = "neutro"
        self._escribe(f"=== Inicio VtT: {len(self.archivos)} archivo(s), modelo '{modelo}', perfil '{opts['perfil']}' ===")
        threading.Thread(target=self._worker_vtt,
                         args=(list(self.archivos), modelo, idioma, salida, formatos,
                               self.v_vad.get(), self.v_words.get(), opts), daemon=True).start()

    def _worker_vtt(self, archivos, modelo, idioma, salida, formatos, vad, words, opts):
        try:
            from faster_whisper import BatchedInferencePipeline, WhisperModel
            perfil_nombre = opts.get("perfil") if opts.get("perfil") in core.PERFILES else "Equilibrado"
            perfil = core.PERFILES[perfil_nombre]
            device, compute = self._backend(); backend_key = (modelo, device, compute)
            if self.modelo is None or self._modelo_backend != backend_key:
                try:
                    self.cola.put(("log", f"Cargando '{modelo}' en {device}/{compute}…"))
                    self.modelo = WhisperModel(modelo, device=device, compute_type=compute)
                except Exception:
                    if device != "cuda": raise
                    self.cola.put(("log", "GPU no utilizable; se vuelve a CPU int8."))
                    device, compute = "cpu", "int8"; backend_key = (modelo, device, compute)
                    self.modelo = WhisperModel(modelo, device=device, compute_type=compute)
                self.modelo_nombre = modelo; self._modelo_backend = backend_key
            motor = BatchedInferencePipeline(model=self.modelo) if perfil["batched"] else self.modelo
            correctos = fallidos = 0
            for i, archivo in enumerate(archivos, 1):
                if self.cancelar.is_set(): raise base.Cancelado()
                nombre = Path(archivo).name; t0 = time.time(); seg_objs = []; partes = []
                self.cola.put(("status", f"Transcribiendo {i}/{len(archivos)}: {nombre}")); self.cola.put(("progress", 0))
                try:
                    kwargs = dict(language=idioma, vad_filter=vad, word_timestamps=words,
                                  beam_size=int(perfil["beam_size"]),
                                  hotwords=core.glosario_a_hotwords(opts.get("glosario", "")))
                    if perfil["batched"]:
                        segments, info = motor.transcribe(archivo, batch_size=int(perfil["batch_size"]), **kwargs)
                    else:
                        segments, info = motor.transcribe(archivo, **kwargs)
                    dur = float(info.duration or 0); self.dur_actual = dur; self.t_transcripcion_inicio = t0
                    for s in segments:
                        if self.cancelar.is_set(): raise base.Cancelado()
                        seg_objs.append(s); partes.append(s.text)
                        if dur: self.cola.put(("progress", min(100.0, s.end / dur * 100)))
                        self.cola.put(("segmento", (s.start, s.end, s.text)))
                    texto = core.limpiar_texto(" ".join(partes)); segs = core.segmentos_a_dicts(seg_objs)
                    speakers: List[Dict[str, Any]] = []
                    if opts.get("diarizar") and segs:
                        ns = -1 if opts.get("num_speakers") == "Auto" else int(opts["num_speakers"])
                        self.cola.put(("status", f"Identificando hablantes: {nombre}"))
                        turnos = diar.diarizar(archivo, base.CARPETA_DATOS / "modelos_hablantes", ns,
                                              log=lambda x: self.cola.put(("log", x)))
                        segs, speakers = core.asignar_hablantes(segs, turnos)
                    bloques = core.agrupar_segmentos(segs, max_segundos=float(opts["max_bloque"]),
                                                     pausa_corte=float(opts["pausa_bloque"]))
                    metricas = core.calcular_metricas(dur, time.time() - t0, device=device, compute_type=compute,
                                                      batched=bool(perfil["batched"]), batch_size=int(perfil["batch_size"]),
                                                      beam_size=int(perfil["beam_size"]))
                    out = Path(salida) if salida else (base.CARPETA_TRANSCRIPCIONES if self._es_temporal(archivo)
                                                       else Path(archivo).parent)
                    escritos, paths = self._escribir_vtt(out, archivo, modelo, idioma, texto, segs, bloques,
                                                         speakers, metricas, formatos, perfil_nombre, opts.get("glosario", ""))
                    self.ultima_salida = str(out); self.cola.put(("salida_nueva", str(out))); self.cola.put(("progress", 100))
                    velocidad = metricas.get("speed_x") or 0
                    self.cola.put(("log", f"OK {nombre}: {len(segs)} segmentos → {len(bloques)} bloques · {velocidad:.2f}× tiempo real"))
                    for e in escritos: self.cola.put(("log", f"  -> {e}"))
                    self.ultima_revision = {"source": archivo, "model": modelo, "language": idioma or "auto",
                                            "text": texto, "segments": segs, "blocks": bloques,
                                            "speakers": speakers, "metrics": metricas, "profile": perfil_nombre,
                                            "hotwords": opts.get("glosario", ""), "paths": paths}
                    correctos += 1
                except base.Cancelado:
                    if seg_objs:
                        try:
                            segs = core.segmentos_a_dicts(seg_objs)
                            texto = core.limpiar_texto(" ".join(partes))
                            bloques = core.agrupar_segmentos(
                                segs, max_segundos=float(opts["max_bloque"]),
                                pausa_corte=float(opts["pausa_bloque"]))
                            metricas = core.calcular_metricas(
                                self.dur_actual, time.time() - t0, device=device,
                                compute_type=compute, partial=True)
                            out = Path(salida) if salida else (
                                base.CARPETA_TRANSCRIPCIONES if self._es_temporal(archivo)
                                else Path(archivo).parent)
                            parcial = str(Path(archivo).with_name(
                                Path(archivo).stem + "_PARCIAL" + Path(archivo).suffix))
                            escritos, _ = self._escribir_vtt(
                                out, parcial, modelo, idioma, texto, segs, bloques, [],
                                metricas, formatos, perfil_nombre, opts.get("glosario", ""))
                            self.cola.put(("log", f"PARCIAL {nombre}: " + ", ".join(escritos)))
                        except Exception:
                            self.cola.put(("log", "No se pudo guardar el parcial:\n" + traceback.format_exc()))
                    raise
                except Exception:
                    self.cola.put(("log", f"ERROR {nombre}:\n{traceback.format_exc()}")); self.cola.put(("archivo_fallido", nombre)); fallidos += 1
            if correctos == 0 and fallidos:
                self.cola.put(("lote_error", "No se pudo transcribir ningún archivo."))
            elif fallidos:
                self.cola.put(("lote_parcial", (correctos, fallidos)))
            else:
                self.cola.put(("log", f"=== Completado: {correctos} archivo(s) ==="))
        except base.Cancelado:
            self.cola.put(("cancelado", None))
        except ModuleNotFoundError as e:
            self.cola.put(("dep_error", (e.name or "faster_whisper", "la transcripción")))
        except Exception:
            self.cola.put(("error", traceback.format_exc()))
        finally:
            self.cola.put(("done", None))

    def _escribir_vtt(self, out, archivo, modelo, idioma, texto, segs, bloques, speakers,
                      metricas, formatos, perfil, glosario):
        out.mkdir(parents=True, exist_ok=True); tronco = self._tronco_salida_disponible(out, archivo, formatos)
        escritos: List[str] = []; paths: Dict[str, str] = {}
        def p(ext): return tronco.with_name(tronco.name + "." + ext)
        if formatos.get("txt"):
            x=p("txt"); x.write_text(core.texto_bloques(bloques), encoding="utf-8"); escritos.append(x.name); paths["txt"]=str(x)
        if formatos.get("md"):
            x=p("md"); x.write_text(core.markdown_bloques(archivo, modelo, idioma, bloques, metricas), encoding="utf-8"); escritos.append(x.name); paths["md"]=str(x)
        if formatos.get("srt"):
            x=p("srt"); x.write_text(core.srt_segmentos(segs), encoding="utf-8"); escritos.append(x.name); paths["srt"]=str(x)
        if formatos.get("vtt"):
            x=p("vtt"); x.write_text(core.vtt_segmentos(segs), encoding="utf-8"); escritos.append(x.name); paths["vtt"]=str(x)
        doc = core.documento_json(archivo, modelo, idioma, texto, segs, bloques, speakers, metricas, perfil, glosario)
        if formatos.get("json"):
            x=p("json"); x.write_text(core.json_texto(doc), encoding="utf-8"); escritos.append(x.name); paths["json"]=str(x)
        if formatos.get("docx"):
            x=p("docx"); core.escribir_docx(x, archivo, modelo, idioma, bloques, metricas); escritos.append(x.name); paths["docx"]=str(x)
        return escritos, paths

    def _revision(self):
        rev = self.ultima_revision
        if not rev:
            messagebox.showinfo("Revisión", "Primero transcribe un archivo en esta sesión."); return
        w=tk.Toplevel(self.root); w.title(f"Revisión — {Path(rev['source']).name}"); w.geometry("1050x600")
        f=ttk.Frame(w,padding=10); f.pack(fill="both",expand=True)
        ttk.Label(f,text="Doble clic: reproducir ~12 s. [REVISAR] indica baja confianza ASR.").pack(fill="x",pady=(0,8))
        tree=ttk.Treeview(f,columns=("hora","hablante","estado","texto"),show="headings")
        for c,t,a in (("hora","Tiempo",90),("hablante","Hablante",130),("estado","Estado",80),("texto","Texto",700)):
            tree.heading(c,text=t); tree.column(c,width=a,stretch=(c=="texto"))
        tree.pack(fill="both",expand=True)
        def llenar():
            tree.delete(*tree.get_children())
            for i,b in enumerate(rev["blocks"]):
                tree.insert("","end",iid=str(i),values=(core.ts_simple(b["start"]),b.get("speaker") or "—",
                    "REVISAR" if b.get("review_required") else "",b.get("text", "")))
        llenar()
        def play(_=None):
            if tree.selection(): self._play(rev["source"], float(rev["blocks"][int(tree.selection()[0])]["start"]))
        def renombrar():
            if not tree.selection(): return
            actual=rev["blocks"][int(tree.selection()[0])].get("speaker")
            if not actual: return
            nuevo=simpledialog.askstring("Renombrar hablante",f"Nuevo nombre para {actual}:",parent=w)
            if not nuevo or not nuevo.strip(): return
            nuevo=nuevo.strip()
            for grupo in (rev["blocks"],rev["segments"]):
                for x in grupo:
                    if x.get("speaker")==actual: x["speaker"]=nuevo
            for x in rev["speakers"]:
                if x.get("display_name")==actual: x["display_name"]=nuevo
            llenar()
        tree.bind("<Double-1>",play); b=ttk.Frame(f); b.pack(fill="x",pady=(8,0))
        ttk.Button(b,text="▶ Reproducir",command=play).pack(side="left")
        ttk.Button(b,text="■ Detener",command=self._stop_audio).pack(side="left",padx=6)
        ttk.Button(b,text="Renombrar hablante",command=renombrar).pack(side="left",padx=6)
        ttk.Button(b,text="Exportar revisión…",command=lambda:self._exportar_revision(rev,w)).pack(side="right")

    def _play(self, archivo, inicio):
        def trabajo():
            try:
                import sounddevice as sd
                data, rate = core.extraer_audio_revision(archivo, inicio, 12.0); sd.stop(); sd.play(data, rate, blocking=False)
            except Exception as exc:
                self.cola.put(("log", f"No se pudo reproducir revisión: {exc}"))
        threading.Thread(target=trabajo,daemon=True).start()

    def _stop_audio(self):
        try:
            import sounddevice as sd; sd.stop()
        except Exception: pass

    def _exportar_revision(self, rev, parent):
        carpeta=filedialog.askdirectory(title="Carpeta para exportar revisión",parent=parent)
        if not carpeta: return
        stem=Path(carpeta)/(Path(rev["source"]).stem+"_revision_"+datetime.now().strftime("%Y%m%d_%H%M%S"))
        stem.with_suffix(".txt").write_text(core.texto_bloques(rev["blocks"]),encoding="utf-8")
        stem.with_suffix(".md").write_text(core.markdown_bloques(rev["source"],rev["model"],rev["language"],rev["blocks"],rev["metrics"]),encoding="utf-8")
        doc=core.documento_json(rev["source"],rev["model"],rev["language"],rev["text"],rev["segments"],rev["blocks"],rev["speakers"],rev["metrics"],rev["profile"],rev["hotwords"])
        doc["review"]["edited"]=True; stem.with_suffix(".json").write_text(core.json_texto(doc),encoding="utf-8")
        core.escribir_docx(stem.with_suffix(".docx"),rev["source"],rev["model"],rev["language"],rev["blocks"],rev["metrics"])
        messagebox.showinfo("Revisión exportada",f"Se creó una copia revisada en:\n{carpeta}",parent=parent)

    def _cerrar(self):
        self._stop_audio(); super()._cerrar()


def main():
    try:
        from tkinterdnd2 import TkinterDnD
        root=TkinterDnD.Tk(); dnd=True
    except Exception:
        root=tk.Tk(); dnd=False
    VtTEnhancedApp(root,dnd); root.mainloop()


if __name__ == "__main__":
    main()
