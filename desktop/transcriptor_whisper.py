#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Transcriptor Whisper v2 - Interfaz grafica (Tkinter, solo stdlib + faster-whisper + yt-dlp).
MULTIPLATAFORMA: funciona en Windows, macOS y Linux sin privilegios de administrador.

Forma recomendada de ejecutar (auto-instala lo necesario la primera vez):
    python run.py        (o doble clic en run.bat / run.sh)

Tambien se puede ejecutar directamente si ya estan las dependencias:
    py -m pip install -U faster-whisper yt-dlp
    python transcriptor_whisper.py

Notas:
  - faster-whisper decodifica audio con PyAV interno -> NO requiere FFmpeg para transcribir.
  - FFmpeg solo se usa (si esta disponible) para mejorar descargas de YouTube via yt-dlp.
  - El modelo se baja una vez en formato CTranslate2 (cache de HuggingFace) y queda en el equipo.
"""

import os
import sys
import time
import json
import wave
import queue
import shutil
import textwrap
import subprocess
import tempfile
import threading
import traceback
from datetime import datetime
from pathlib import Path

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

MODELOS = ["tiny", "base", "small", "medium", "large-v3"]
IDIOMAS = {
    "Espanol": "es",
    "Ingles": "en",
    "Portugues": "pt",
    "Frances": "fr",
    "Deteccion automatica": None,
}
EXTS = (".mp3", ".wav", ".m4a", ".ogg", ".flac", ".mp4", ".aac",
        ".wma", ".opus", ".webm", ".mkv", ".avi")
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
CONFIG_PATH = Path(__file__).parent / "transcriptor_config.json"

# Paleta moderna (violeta vibrante + superficies claras), minimalista.
PALETA = {
    "bg": "#F4F2FB",
    "surface": "#FFFFFF",
    "primary": "#6C4DF2",
    "primary_dark": "#5538D6",
    "primary_soft": "#ECE8FB",
    "text": "#1B1B1F",
    "muted": "#6B6878",
    "border": "#DED9F0",
    "trough": "#E7E2F7",
}


class Cancelado(Exception):
    pass


def fecha_es():
    n = datetime.now()
    return f"{n.day} de {MESES[n.month - 1]} de {n.year} {n.hour:02d}:{n.minute:02d}"


def ts_simple(t):
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def ts_srt(t):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def ts_vtt(t):
    return ts_srt(t).replace(",", ".")


# Ancho de linea para el .txt (y el texto completo del .md). 0 = sin ajuste.
ANCHO_TXT = 100


def envolver_texto(texto, ancho=ANCHO_TXT):
    """Ajusta el texto a un ancho legible para no tener que desplazarse al lado."""
    if not ancho or ancho <= 0:
        return texto
    salida = []
    for parrafo in texto.splitlines() or [texto]:
        if parrafo.strip():
            salida.append(textwrap.fill(parrafo, width=ancho))
        else:
            salida.append("")
    return "\n".join(salida)


def abrir_en_explorador(ruta):
    """Abre una carpeta en el explorador de archivos del sistema (Windows/macOS/Linux)."""
    try:
        if sys.platform.startswith("win"):
            os.startfile(ruta)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", ruta])
        else:
            subprocess.Popen(["xdg-open", ruta])
        return True
    except Exception:
        return False


def detectar_ffmpeg():
    enc = shutil.which("ffmpeg")
    if enc:
        return str(Path(enc).parent)
    for c in [Path.home() / "ffmpeg" / "bin", Path.home() / "ffmpeg",
              Path(__file__).parent / "ffmpeg" / "bin", Path(__file__).parent / "ffmpeg"]:
        if (c / "ffmpeg.exe").exists() or (c / "ffmpeg").exists():
            return str(c)
    return None


def cargar_config():
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def guardar_config(d):
    try:
        CONFIG_PATH.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


class TranscriptorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Transcriptor Whisper v2")
        self.root.geometry("820x780")
        self.root.minsize(720, 660)

        self.cola = queue.Queue()
        self.archivos = []
        self.ffmpeg_dir = None
        self.modelo = None
        self.modelo_nombre = None
        self.transcribiendo = False
        self.bajando_yt = False
        self.ultima_salida = None
        self.cancelar = threading.Event()
        self.temp_dirs = []

        # Estado de grabacion desde el microfono / entrada de audio.
        self.grabando = False
        self.grabador = None
        self.wave_file = None
        self.t_grab_inicio = 0.0
        self.ruta_grab = None
        self.entradas = []

        self.cfg = cargar_config()
        self._ui()
        self._init_ffmpeg()
        self._aplicar_config()
        self.root.protocol("WM_DELETE_WINDOW", self._cerrar)
        self.root.after(120, self._procesar_cola)

    def _ui(self):
        pad = {"padx": 8, "pady": 4}
        cont = ttk.Frame(self.root, padding=14)
        cont.pack(fill="both", expand=True)

        header = ttk.Frame(cont)
        header.pack(fill="x", padx=4, pady=(0, 10))
        ttk.Label(header, text="🎙  Transcriptor Whisper", style="Title.TLabel").pack(anchor="w")
        ttk.Label(header, text="Voz a texto en tu equipo · privado y sin conexión",
                  style="Subtitle.TLabel").pack(anchor="w")

        fr_ff = ttk.LabelFrame(cont, text="FFmpeg (opcional, solo mejora descargas de YouTube)", padding=8)
        fr_ff.pack(fill="x", **pad)
        self.lbl_ff = ttk.Label(fr_ff, text="Detectando...", foreground="gray")
        self.lbl_ff.pack(side="left", fill="x", expand=True)
        ttk.Button(fr_ff, text="Seleccionar carpeta bin", command=self._elegir_ffmpeg).pack(side="right")

        fr_yt = ttk.LabelFrame(cont, text="YouTube", padding=8)
        fr_yt.pack(fill="x", **pad)
        self.var_url = tk.StringVar(value="")
        ttk.Entry(fr_yt, textvariable=self.var_url).pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.btn_yt = ttk.Button(fr_yt, text="Descargar audio y agregar", command=self._descargar_yt)
        self.btn_yt.pack(side="right")

        fr_rec = ttk.LabelFrame(cont, text="Grabar desde micrófono / entrada de audio", padding=8)
        fr_rec.pack(fill="x", **pad)
        ttk.Label(fr_rec, text="Entrada:").pack(side="left")
        self.cmb_dev = ttk.Combobox(fr_rec, state="readonly", width=32)
        self.cmb_dev.pack(side="left", padx=(4, 8))
        self.entradas = self._dispositivos_entrada()
        self.cmb_dev["values"] = ["Predeterminada"] + [n for _, n in self.entradas]
        self.cmb_dev.current(0)
        self.btn_grab = ttk.Button(fr_rec, text="●  Grabar", command=self._toggle_grabar)
        self.btn_grab.pack(side="left")
        self.lbl_grab_t = ttk.Label(fr_rec, text="00:00", style="Subtitle.TLabel")
        self.lbl_grab_t.pack(side="left", padx=10)

        fr_files = ttk.LabelFrame(cont, text="Archivos de audio / video", padding=8)
        fr_files.pack(fill="both", expand=True, **pad)
        self.lst = tk.Listbox(fr_files, height=6, selectmode="extended",
                              bg=PALETA["surface"], fg=PALETA["text"], borderwidth=0,
                              highlightthickness=1, highlightbackground=PALETA["border"],
                              selectbackground=PALETA["primary"], selectforeground="#FFFFFF",
                              activestyle="none")
        self.lst.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(fr_files, orient="vertical", command=self.lst.yview)
        sb.pack(side="left", fill="y")
        self.lst.config(yscrollcommand=sb.set)
        fr_b = ttk.Frame(fr_files)
        fr_b.pack(side="right", fill="y", padx=(8, 0))
        ttk.Button(fr_b, text="Agregar", command=self._agregar).pack(fill="x", pady=2)
        ttk.Button(fr_b, text="Quitar", command=self._quitar).pack(fill="x", pady=2)
        ttk.Button(fr_b, text="Limpiar", command=self._limpiar).pack(fill="x", pady=2)

        fr_o = ttk.LabelFrame(cont, text="Opciones", padding=8)
        fr_o.pack(fill="x", **pad)
        ttk.Label(fr_o, text="Modelo:").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.cmb_m = ttk.Combobox(fr_o, values=MODELOS, state="readonly", width=12)
        self.cmb_m.set("small")
        self.cmb_m.grid(row=0, column=1, sticky="w", padx=4, pady=4)
        ttk.Label(fr_o, text="Idioma:").grid(row=0, column=2, sticky="w", padx=4, pady=4)
        self.cmb_i = ttk.Combobox(fr_o, values=list(IDIOMAS.keys()), state="readonly", width=22)
        self.cmb_i.set("Espanol")
        self.cmb_i.grid(row=0, column=3, sticky="w", padx=4, pady=4)

        self.v_txt = tk.BooleanVar(value=True)
        self.v_md = tk.BooleanVar(value=False)
        self.v_srt = tk.BooleanVar(value=False)
        self.v_vtt = tk.BooleanVar(value=False)
        ttk.Label(fr_o, text="Formatos:").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        fr_fmt = ttk.Frame(fr_o)
        fr_fmt.grid(row=1, column=1, columnspan=3, sticky="w")
        ttk.Checkbutton(fr_fmt, text=".txt", variable=self.v_txt).pack(side="left", padx=6)
        ttk.Checkbutton(fr_fmt, text=".md (Obsidian)", variable=self.v_md).pack(side="left", padx=6)
        ttk.Checkbutton(fr_fmt, text=".srt", variable=self.v_srt).pack(side="left", padx=6)
        ttk.Checkbutton(fr_fmt, text=".vtt", variable=self.v_vtt).pack(side="left", padx=6)

        self.v_vad = tk.BooleanVar(value=True)
        self.v_words = tk.BooleanVar(value=False)
        fr_adv = ttk.Frame(fr_o)
        fr_adv.grid(row=2, column=1, columnspan=3, sticky="w")
        ttk.Checkbutton(fr_adv, text="Filtro de silencios (VAD, recomendado)", variable=self.v_vad).pack(side="left", padx=6)
        ttk.Checkbutton(fr_adv, text="Marcas por palabra (mas lento)", variable=self.v_words).pack(side="left", padx=6)

        ttk.Label(fr_o, text="Carpeta de salida:").grid(row=3, column=0, sticky="w", padx=4, pady=4)
        self.v_out = tk.StringVar(value="")
        ttk.Entry(fr_o, textvariable=self.v_out).grid(row=3, column=1, columnspan=2, sticky="we", padx=4, pady=4)
        ttk.Button(fr_o, text="Examinar", command=self._elegir_salida).grid(row=3, column=3, sticky="w", padx=4)
        ttk.Label(fr_o, text="(vacio = junto a cada audio)", foreground="gray").grid(row=4, column=1, columnspan=2, sticky="w", padx=4)
        fr_o.columnconfigure(1, weight=1)

        fr_a = ttk.Frame(cont)
        fr_a.pack(fill="x", **pad)
        self.btn_run = ttk.Button(fr_a, text="Transcribir", command=self._iniciar, style="Accent.TButton")
        self.btn_run.pack(side="left")
        self.btn_cancel = ttk.Button(fr_a, text="Cancelar", command=self._cancelar, state="disabled")
        self.btn_cancel.pack(side="left", padx=8)
        self.btn_open = ttk.Button(fr_a, text="Abrir carpeta de salida", command=self._abrir_salida, state="disabled")
        self.btn_open.pack(side="left", padx=8)
        self.pb = ttk.Progressbar(fr_a, mode="determinate", maximum=100, length=200)
        self.pb.pack(side="right", fill="x", expand=True, padx=8)

        self.lbl_st = ttk.Label(cont, text="Listo.", foreground="gray")
        self.lbl_st.pack(fill="x", padx=8)

        fr_l = ttk.LabelFrame(cont, text="Registro", padding=8)
        fr_l.pack(fill="both", expand=True, **pad)
        self.log = scrolledtext.ScrolledText(fr_l, height=8, state="disabled", wrap="word",
                                             bg=PALETA["surface"], fg=PALETA["text"], borderwidth=0,
                                             highlightthickness=1, highlightbackground=PALETA["border"],
                                             insertbackground=PALETA["text"])
        self.log.pack(fill="both", expand=True)

    def _aplicar_config(self):
        c = self.cfg
        if c.get("modelo") in MODELOS:
            self.cmb_m.set(c["modelo"])
        if c.get("idioma") in IDIOMAS:
            self.cmb_i.set(c["idioma"])
        if c.get("salida"):
            self.v_out.set(c["salida"])
        for k, var in [("txt", self.v_txt), ("md", self.v_md), ("srt", self.v_srt),
                       ("vtt", self.v_vtt), ("vad", self.v_vad), ("words", self.v_words)]:
            if k in c:
                var.set(bool(c[k]))

    def _snapshot_config(self):
        guardar_config({
            "modelo": self.cmb_m.get(),
            "idioma": self.cmb_i.get(),
            "salida": self.v_out.get().strip(),
            "txt": self.v_txt.get(), "md": self.v_md.get(),
            "srt": self.v_srt.get(), "vtt": self.v_vtt.get(),
            "vad": self.v_vad.get(), "words": self.v_words.get(),
        })

    def _init_ffmpeg(self):
        d = detectar_ffmpeg()
        if d:
            self.ffmpeg_dir = d
            self.lbl_ff.config(text=f"Detectado: {d}", foreground="green")
        else:
            self.lbl_ff.config(text="No detectado (la transcripcion no lo necesita).", foreground="gray")

    def _elegir_ffmpeg(self):
        d = filedialog.askdirectory(title="Carpeta que contiene ffmpeg")
        if not d:
            return
        if (Path(d) / "ffmpeg.exe").exists() or (Path(d) / "ffmpeg").exists():
            self.ffmpeg_dir = d
            self.lbl_ff.config(text=f"Detectado: {d}", foreground="green")
        else:
            messagebox.showerror("FFmpeg", "No se encontro ffmpeg en esa carpeta.")

    def _agregar(self):
        rutas = filedialog.askopenfilenames(
            title="Selecciona audios",
            filetypes=[("Audio/Video", " ".join("*" + e for e in EXTS)), ("Todos", "*.*")])
        for r in rutas:
            self._insertar_archivo(r)

    def _insertar_archivo(self, r):
        if r not in self.archivos:
            self.archivos.append(r)
            self.lst.insert("end", r)

    def _quitar(self):
        for i in reversed(self.lst.curselection()):
            del self.archivos[i]
            self.lst.delete(i)

    def _limpiar(self):
        self.archivos.clear()
        self.lst.delete(0, "end")

    def _elegir_salida(self):
        d = filedialog.askdirectory(title="Carpeta de salida")
        if d:
            self.v_out.set(d)

    def _abrir_salida(self):
        if self.ultima_salida and os.path.isdir(self.ultima_salida):
            if not abrir_en_explorador(self.ultima_salida):
                messagebox.showinfo("Carpeta de salida", self.ultima_salida)

    def _descargar_yt(self):
        if self.bajando_yt:
            return
        url = self.var_url.get().strip()
        if not url:
            messagebox.showwarning("URL", "Pega una URL de YouTube.")
            return
        self.bajando_yt = True
        self.btn_yt.config(state="disabled")
        self._escribe(f"Descargando audio de: {url}")
        threading.Thread(target=self._worker_yt, args=(url,), daemon=True).start()

    def _worker_yt(self, url):
        try:
            import yt_dlp
            tmp = tempfile.mkdtemp(prefix="ytw_")
            self.temp_dirs.append(tmp)
            opts = {
                "format": "bestaudio/best",
                "outtmpl": os.path.join(tmp, "%(title).80s.%(ext)s"),
                "noplaylist": True,
                "quiet": True,
                "no_warnings": True,
            }
            if self.ffmpeg_dir:
                opts["ffmpeg_location"] = self.ffmpeg_dir
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                ruta = ydl.prepare_filename(info)
            if not os.path.exists(ruta):
                hijos = list(Path(tmp).iterdir())
                if hijos:
                    ruta = str(hijos[0])
            self.cola.put(("yt_ok", ruta))
        except Exception:
            self.cola.put(("yt_err", traceback.format_exc()))

    # ----- Grabacion desde el microfono / entrada de audio -----
    def _dispositivos_entrada(self):
        """Lista los dispositivos de ENTRADA (microfono, linea), no la salida."""
        try:
            import sounddevice as sd
            devs = sd.query_devices()
            return [(i, d["name"]) for i, d in enumerate(devs)
                    if d.get("max_input_channels", 0) > 0]
        except Exception:
            return []

    def _dev_seleccionado(self):
        try:
            sel = self.cmb_dev.current()
        except Exception:
            sel = 0
        if sel <= 0:
            return None  # entrada predeterminada del sistema
        try:
            return self.entradas[sel - 1][0]
        except Exception:
            return None

    def _toggle_grabar(self):
        if self.grabando:
            self._detener_grabacion()
        else:
            self._iniciar_grabacion()

    def _iniciar_grabacion(self):
        try:
            import sounddevice as sd
        except Exception:
            messagebox.showerror(
                "Grabación",
                "Falta el módulo 'sounddevice'.\n\n"
                "Cierra la app y ejecuta:  python run.py --update\n"
                "(en Linux también: sudo apt install libportaudio2)")
            return

        dev = self._dev_seleccionado()
        base = self.v_out.get().strip()
        if base and os.path.isdir(base):
            carpeta = base
        else:
            carpeta = tempfile.mkdtemp(prefix="grab_")
            self.temp_dirs.append(carpeta)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.ruta_grab = os.path.join(carpeta, f"grabacion_{ts}.wav")

        def callback(indata, frames, tinfo, status):
            wf = self.wave_file
            if wf is not None:
                try:
                    wf.writeframes(bytes(indata))
                except Exception:
                    pass

        # Intenta 16 kHz mono (ideal para Whisper); si el dispositivo no lo admite,
        # usa su frecuencia por defecto (Whisper la remuestrea igual).
        rate = 16000
        try:
            self.grabador = sd.RawInputStream(
                samplerate=rate, channels=1, dtype="int16", device=dev, callback=callback)
        except Exception:
            try:
                info = sd.query_devices(dev, "input") if dev is not None else sd.query_devices(kind="input")
                rate = int(info.get("default_samplerate", 44100)) or 44100
            except Exception:
                rate = 44100
            try:
                self.grabador = sd.RawInputStream(
                    samplerate=rate, channels=1, dtype="int16", device=dev, callback=callback)
            except Exception:
                self.grabador = None
                messagebox.showerror("Grabación",
                                     "No se pudo abrir el dispositivo de entrada seleccionado.")
                return

        try:
            self.wave_file = wave.open(self.ruta_grab, "wb")
            self.wave_file.setnchannels(1)
            self.wave_file.setsampwidth(2)
            self.wave_file.setframerate(rate)
            self.grabador.start()
        except Exception:
            self._cerrar_grabador()
            messagebox.showerror("Grabación", "No se pudo iniciar la grabación.")
            return

        self.grabando = True
        self.t_grab_inicio = time.time()
        self.btn_grab.config(text="■  Detener")
        self._escribe(f"Grabando desde la entrada ({rate} Hz) -> {Path(self.ruta_grab).name}")
        self.lbl_st.config(text="Grabando... pulsa Detener para finalizar.", foreground="gray")
        self._tick_grab()

    def _detener_grabacion(self):
        self.grabando = False
        self._cerrar_grabador()
        self.btn_grab.config(text="●  Grabar")
        self.lbl_grab_t.config(text="00:00")
        if self.ruta_grab and os.path.exists(self.ruta_grab) and os.path.getsize(self.ruta_grab) > 44:
            self._insertar_archivo(self.ruta_grab)
            self._escribe(f"Grabación guardada y agregada: {Path(self.ruta_grab).name}")
            self.lbl_st.config(text="Grabación lista. Ya puedes transcribirla.", foreground="gray")
        else:
            self._escribe("Grabación vacía o no guardada.")
        self.ruta_grab = None

    def _cerrar_grabador(self):
        try:
            if self.grabador is not None:
                self.grabador.stop()
                self.grabador.close()
        except Exception:
            pass
        self.grabador = None
        try:
            if self.wave_file is not None:
                self.wave_file.close()
        except Exception:
            pass
        self.wave_file = None

    def _tick_grab(self):
        if not self.grabando:
            return
        seg = int(time.time() - self.t_grab_inicio)
        self.lbl_grab_t.config(text=f"{seg // 60:02d}:{seg % 60:02d}")
        self.root.after(500, self._tick_grab)

    def _iniciar(self):
        if self.transcribiendo:
            return
        if not self.archivos:
            messagebox.showwarning("Sin archivos", "Agrega al menos un audio.")
            return
        if not (self.v_txt.get() or self.v_md.get() or self.v_srt.get() or self.v_vtt.get()):
            messagebox.showwarning("Formato", "Marca al menos un formato de salida.")
            return
        salida = self.v_out.get().strip() or None
        if salida and not os.path.isdir(salida):
            messagebox.showerror("Salida", "La carpeta de salida no existe.")
            return

        self._snapshot_config()
        idioma = IDIOMAS[self.cmb_i.get()]
        modelo = self.cmb_m.get()
        formatos = {"txt": self.v_txt.get(), "md": self.v_md.get(),
                    "srt": self.v_srt.get(), "vtt": self.v_vtt.get()}

        self.transcribiendo = True
        self.cancelar.clear()
        self.btn_run.config(state="disabled")
        self.btn_cancel.config(state="normal")
        self.btn_open.config(state="disabled")
        self.pb["value"] = 0
        self._escribe(f"=== Inicio: {len(self.archivos)} archivo(s), modelo '{modelo}' ===")

        args = (list(self.archivos), modelo, idioma, salida, formatos,
                self.v_vad.get(), self.v_words.get())
        threading.Thread(target=self._worker, args=args, daemon=True).start()

    def _worker(self, archivos, modelo, idioma, salida, formatos, vad, words):
        try:
            self.cola.put(("log", "Importando faster-whisper (la primera vez puede tardar)..."))
            from faster_whisper import WhisperModel

            if self.modelo is None or self.modelo_nombre != modelo:
                self.cola.put(("log", f"Cargando modelo '{modelo}' (descarga solo la primera vez)..."))
                self.modelo = WhisperModel(modelo, device="cpu", compute_type="int8")
                self.modelo_nombre = modelo

            total = len(archivos)
            for i, archivo in enumerate(archivos, 1):
                if self.cancelar.is_set():
                    raise Cancelado()
                nombre = Path(archivo).name
                self.cola.put(("status", f"Transcribiendo {i}/{total}: {nombre}"))
                self.cola.put(("progress", 0))
                t0 = time.time()

                segments, info = self.modelo.transcribe(
                    archivo, language=idioma, vad_filter=vad, word_timestamps=words)
                dur = info.duration or 0

                segs = []
                partes = []
                for seg in segments:
                    if self.cancelar.is_set():
                        raise Cancelado()
                    segs.append(seg)
                    partes.append(seg.text)
                    if dur:
                        self.cola.put(("progress", min(100.0, seg.end / dur * 100)))
                texto = "".join(partes).strip()

                base = Path(salida) if salida else Path(archivo).parent
                self.ultima_salida = str(base)
                escritos = self._escribir_salidas(base, archivo, modelo, idioma, texto, segs, formatos)
                self.cola.put(("progress", 100))
                for e in escritos:
                    self.cola.put(("log", f"  -> {e}"))
                self.cola.put(("log", f"OK {nombre} ({time.time() - t0:.0f}s)"))

            self.cola.put(("log", "=== Completado ==="))
        except Cancelado:
            self.cola.put(("cancelado", None))
        except Exception:
            self.cola.put(("error", traceback.format_exc()))
        finally:
            self.cola.put(("done", None))

    def _escribir_salidas(self, base, archivo, modelo, idioma, texto, segs, formatos):
        tronco = base / Path(archivo).stem
        escritos = []
        if formatos["txt"]:
            p = tronco.with_suffix(".txt")
            p.write_text(envolver_texto(texto) + "\n", encoding="utf-8")
            escritos.append(p.name)
        if formatos["md"]:
            p = tronco.with_suffix(".md")
            p.write_text(self._fmt_md(archivo, modelo, idioma, texto, segs), encoding="utf-8")
            escritos.append(p.name)
        if formatos["srt"]:
            p = tronco.with_suffix(".srt")
            p.write_text(self._fmt_srt(segs), encoding="utf-8")
            escritos.append(p.name)
        if formatos["vtt"]:
            p = tronco.with_suffix(".vtt")
            p.write_text(self._fmt_vtt(segs), encoding="utf-8")
            escritos.append(p.name)
        return escritos

    def _fmt_md(self, archivo, modelo, idioma, texto, segs):
        lineas = [
            f"# Transcripcion: {Path(archivo).name}",
            "",
            f"- **Modelo:** {modelo}",
            f"- **Idioma:** {idioma or 'auto'}",
            f"- **Fecha:** {fecha_es()}",
            "",
            "## Texto completo",
            "",
            envolver_texto(texto),
            "",
            "## Segmentos",
            "",
        ]
        for s in segs:
            lineas.append(f"- `[{ts_simple(s.start)} -> {ts_simple(s.end)}]` {s.text.strip()}")
        return "\n".join(lineas) + "\n"

    def _fmt_srt(self, segs):
        out = []
        for i, s in enumerate(segs, 1):
            out.append(str(i))
            out.append(f"{ts_srt(s.start)} --> {ts_srt(s.end)}")
            out.append(s.text.strip())
            out.append("")
        return "\n".join(out)

    def _fmt_vtt(self, segs):
        out = ["WEBVTT", ""]
        for s in segs:
            out.append(f"{ts_vtt(s.start)} --> {ts_vtt(s.end)}")
            out.append(s.text.strip())
            out.append("")
        return "\n".join(out)

    def _cancelar(self):
        if self.transcribiendo:
            self.cancelar.set()
            self.lbl_st.config(text="Cancelando...", foreground="gray")

    def _procesar_cola(self):
        try:
            while True:
                tipo, *p = self.cola.get_nowait()
                if tipo == "log":
                    self._escribe(p[0])
                elif tipo == "status":
                    self.lbl_st.config(text=p[0], foreground="gray")
                    self._escribe(p[0])
                elif tipo == "progress":
                    self.pb["value"] = p[0]
                elif tipo == "error":
                    self._escribe("ERROR:\n" + p[0])
                    self.lbl_st.config(text="Error. Revisa el registro.", foreground="red")
                    messagebox.showerror("Error", p[0].strip().splitlines()[-1])
                elif tipo == "cancelado":
                    self._escribe("=== Cancelado por el usuario ===")
                    self.lbl_st.config(text="Cancelado.", foreground="gray")
                elif tipo == "done":
                    self._finalizar()
                elif tipo == "yt_ok":
                    self.bajando_yt = False
                    self.btn_yt.config(state="normal")
                    self._insertar_archivo(p[0])
                    self.var_url.set("")
                    self._escribe(f"Audio agregado: {Path(p[0]).name}")
                elif tipo == "yt_err":
                    self.bajando_yt = False
                    self.btn_yt.config(state="normal")
                    self._escribe("ERROR YouTube:\n" + p[0])
                    messagebox.showerror("YouTube", p[0].strip().splitlines()[-1])
        except queue.Empty:
            pass
        self.root.after(120, self._procesar_cola)

    def _finalizar(self):
        self.transcribiendo = False
        self.btn_run.config(state="normal")
        self.btn_cancel.config(state="disabled")
        if self.ultima_salida:
            self.btn_open.config(state="normal")
        if self.lbl_st.cget("foreground") != "red" and "ancelad" not in self.lbl_st.cget("text"):
            self.lbl_st.config(text="Listo.", foreground="gray")

    def _escribe(self, msg):
        self.log.config(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.config(state="disabled")

    def _cerrar(self):
        if self.grabando:
            self.grabando = False
            self._cerrar_grabador()
        self._snapshot_config()
        for d in self.temp_dirs:
            shutil.rmtree(d, ignore_errors=True)
        self.root.destroy()


def _fuente_ui():
    """Familia tipografica agradable segun el sistema (con respaldo automatico)."""
    if sys.platform.startswith("win"):
        return "Segoe UI"
    if sys.platform == "darwin":
        return "Helvetica Neue"
    return "DejaVu Sans"


def _aplicar_estilo(root):
    """Aplica un estilo plano, moderno y con color (minimalista) a la interfaz."""
    style = ttk.Style()
    try:
        style.theme_use("clam")  # base themeable y consistente entre sistemas
    except Exception:
        pass

    p = PALETA
    fam = _fuente_ui()
    root.configure(bg=p["bg"])

    style.configure(".", background=p["bg"], foreground=p["text"], font=(fam, 10))
    style.configure("TFrame", background=p["bg"])
    style.configure("TLabel", background=p["bg"], foreground=p["text"])
    style.configure("Title.TLabel", background=p["bg"], foreground=p["text"], font=(fam, 17, "bold"))
    style.configure("Subtitle.TLabel", background=p["bg"], foreground=p["muted"], font=(fam, 10))

    style.configure("TLabelframe", background=p["bg"], bordercolor=p["border"], relief="solid", borderwidth=1)
    style.configure("TLabelframe.Label", background=p["bg"], foreground=p["primary"], font=(fam, 10, "bold"))

    style.configure("TButton", background=p["surface"], foreground=p["text"],
                    borderwidth=1, focusthickness=0, padding=(10, 6), relief="flat")
    style.map("TButton",
              background=[("active", p["primary_soft"]), ("disabled", "#EFEDF6")],
              bordercolor=[("active", p["primary"])])

    style.configure("Accent.TButton", background=p["primary"], foreground="#FFFFFF",
                    borderwidth=0, padding=(14, 9), font=(fam, 10, "bold"), relief="flat")
    style.map("Accent.TButton",
              background=[("active", p["primary_dark"]), ("disabled", "#C5BEEC")],
              foreground=[("disabled", "#F2F0FB")])

    style.configure("TCheckbutton", background=p["bg"], foreground=p["text"])
    style.map("TCheckbutton", background=[("active", p["bg"])])
    style.configure("TEntry", fieldbackground=p["surface"], bordercolor=p["border"], padding=4)
    style.configure("TCombobox", fieldbackground=p["surface"], background=p["surface"], padding=4)
    style.configure("TProgressbar", background=p["primary"], troughcolor=p["trough"],
                    bordercolor=p["trough"], lightcolor=p["primary"], darkcolor=p["primary"])
    style.configure("Vertical.TScrollbar", background=p["bg"], troughcolor=p["bg"],
                    bordercolor=p["bg"], arrowcolor=p["muted"])


def main():
    root = tk.Tk()
    _aplicar_estilo(root)
    TranscriptorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
