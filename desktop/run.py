#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lanzador autoinstalable del Transcriptor Whisper.

Solo necesitas tener Python 3.8+ instalado. La primera vez, este script:
  1. Crea un entorno virtual local (.venv) junto a este archivo.
  2. Instala SOLO las dependencias necesarias (faster-whisper, yt-dlp).
  3. Ejecuta la interfaz grafica.

Las siguientes veces no descarga nada: arranca directo (a menos que uses --update).
El modelo de voz se descarga una unica vez la primera vez que transcribes,
y queda guardado en el equipo para usarse sin conexion.

Uso:
    python run.py            # instala (1a vez) y abre la app
    python run.py --update   # reinstala/actualiza las dependencias
"""

import os
import sys
import venv
import subprocess
from pathlib import Path

AQUI = Path(__file__).resolve().parent
VENV_DIR = AQUI / ".venv"
APP = AQUI / "transcriptor_whisper.py"
REQS = AQUI / "requirements.txt"
MARKER = VENV_DIR / ".deps_ok"


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
            print("En Linux puede faltar el paquete 'venv'. Instala, por ejemplo:")
            print("    sudo apt install python3-venv python3-tk")
        print(f"Detalle: {e}")
        sys.exit(1)


def instalar_deps(py: Path):
    print("[2/2] Instalando dependencias (solo la primera vez, requiere internet)...")
    try:
        subprocess.check_call([str(py), "-m", "pip", "install", "--upgrade", "pip"])
        subprocess.check_call([str(py), "-m", "pip", "install", "-r", str(REQS)])
    except subprocess.CalledProcessError as e:
        print(f"\nError instalando dependencias: {e}")
        print("Revisa tu conexion a internet y vuelve a ejecutar 'python run.py'.")
        sys.exit(1)
    MARKER.write_text("ok", encoding="utf-8")


def main():
    if sys.version_info < (3, 8):
        print("Se necesita Python 3.8 o superior. Version actual:",
              ".".join(map(str, sys.version_info[:3])))
        sys.exit(1)

    if not APP.exists():
        print(f"No se encontro la app: {APP}")
        sys.exit(1)

    py = venv_python(VENV_DIR)
    forzar = "--update" in sys.argv

    if not py.exists():
        crear_venv()
        py = venv_python(VENV_DIR)

    if forzar or not MARKER.exists():
        instalar_deps(py)

    # Lanza la interfaz grafica con el Python del entorno virtual.
    print("Abriendo el Transcriptor Whisper...")
    try:
        os.execv(str(py), [str(py), str(APP)])
    except OSError:
        # Respaldo si execv no esta disponible (algunos entornos Windows).
        raise SystemExit(subprocess.call([str(py), str(APP)]))


if __name__ == "__main__":
    main()
