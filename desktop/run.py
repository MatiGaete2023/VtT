#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lanzador autoinstalable de VtT.

Python 3.9+ es el minimo real exigido por faster-whisper actual. El lanzador
crea .venv, instala/actualiza requirements.txt cuando cambia su SHA-256 y abre
la interfaz final sin perder la aplicacion base ni la capa mejorada previa.
"""
import os
import sys
import venv
import hashlib
import subprocess
from pathlib import Path

AQUI = Path(__file__).resolve().parent
VENV_DIR = AQUI / ".venv"
APP = AQUI / "vtt_app.py"
REQS = AQUI / "requirements.txt"
MARKER = VENV_DIR / ".deps_ok"
MODULOS_REQUERIDOS = (
    "faster_whisper", "yt_dlp", "sounddevice", "soundcard", "docx", "sherpa_onnx"
)


def venv_python(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def crear_venv():
    print(f"[1/2] Creando entorno virtual en: {VENV_DIR}")
    try:
        venv.create(VENV_DIR, with_pip=True)
    except Exception as e:
        print("\nNo se pudo crear el entorno virtual.")
        if sys.platform.startswith("linux"):
            print("En Linux puede faltar 'venv'. Instala, por ejemplo:")
            print("    sudo apt install python3-venv python3-tk")
        print(f"Detalle: {e}")
        sys.exit(1)


def hash_requirements() -> str:
    return hashlib.sha256(REQS.read_bytes()).hexdigest()


def deps_al_dia() -> bool:
    if not MARKER.exists():
        return False
    try:
        return MARKER.read_text(encoding="utf-8").strip() == hash_requirements()
    except Exception:
        return False


def entorno_importable(py: Path) -> bool:
    try:
        codigo = "import " + ", ".join(MODULOS_REQUERIDOS)
        return subprocess.run([str(py), "-c", codigo], check=False).returncode == 0
    except OSError:
        return False


def instalar_deps(py: Path):
    print("[2/2] Instalando/actualizando dependencias (requiere internet solo cuando faltan)…")
    try:
        subprocess.check_call([str(py), "-m", "pip", "install", "--upgrade", "pip"])
        subprocess.check_call([str(py), "-m", "pip", "install", "--upgrade", "-r", str(REQS)])
    except subprocess.CalledProcessError as e:
        print(f"\nError instalando dependencias: {e}")
        print("Revisa tu conexión y vuelve a ejecutar 'python run.py'.")
        sys.exit(1)
    if not entorno_importable(py):
        print("\nLas dependencias se instalaron, pero una no se puede importar.")
        print("Ejecuta de nuevo: python run.py --update")
        sys.exit(1)
    MARKER.write_text(hash_requirements(), encoding="utf-8")


def main():
    if sys.version_info < (3, 9):
        print("Se necesita Python 3.9 o superior. Versión actual:",
              ".".join(map(str, sys.version_info[:3])))
        sys.exit(1)

    if not APP.exists():
        print(f"No se encontró la app: {APP}")
        sys.exit(1)

    py = venv_python(VENV_DIR)
    forzar = "--update" in sys.argv or "--repair" in sys.argv
    if not py.exists():
        crear_venv()
        py = venv_python(VENV_DIR)
    if forzar or not deps_al_dia() or not entorno_importable(py):
        instalar_deps(py)

    print("Abriendo VtT…")
    try:
        raise SystemExit(subprocess.call([str(py), str(APP)]))
    except OSError:
        print("\nNo se pudo abrir la aplicación con el entorno instalado.")
        print(f"Intenta ejecutar manualmente:\n    {py} {APP}")
        sys.exit(1)


if __name__ == "__main__":
    main()
