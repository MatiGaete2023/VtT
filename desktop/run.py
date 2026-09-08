#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lanzador autoinstalable del Transcriptor Whisper.

Solo necesitas tener Python 3.8+ instalado. La primera vez, este script:
  1. Crea un entorno virtual local (.venv) junto a este archivo.
  2. Instala SOLO las dependencias necesarias (requirements.txt).
  3. Ejecuta la interfaz grafica.

Las siguientes veces no descarga nada: arranca directo. Si requirements.txt
cambio desde la ultima instalacion (por ejemplo, se agrego una dependencia
nueva), lo detecta solo y reinstala automaticamente, sin pasos manuales.
El modelo de voz se descarga una unica vez la primera vez que transcribes,
y queda guardado en el equipo para usarse sin conexion.

Uso:
    python run.py            # instala/actualiza si hace falta y abre la app
    python run.py --update   # fuerza la reinstalacion de las dependencias
"""

import os
import sys
import venv
import hashlib
import subprocess
from pathlib import Path

AQUI = Path(__file__).resolve().parent
VENV_DIR = AQUI / ".venv"
APP = AQUI / "transcriptor_whisper.py"
REQS = AQUI / "requirements.txt"
MARKER = VENV_DIR / ".deps_ok"
MODULOS_REQUERIDOS = ("faster_whisper", "yt_dlp", "sounddevice", "soundcard")


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


def hash_requirements() -> str:
    return hashlib.sha256(REQS.read_bytes()).hexdigest()


def deps_al_dia() -> bool:
    """True si ya se instalaron las dependencias de la version ACTUAL de
    requirements.txt. Si requirements.txt cambio (nueva dependencia agregada
    como sounddevice/soundcard), el hash no coincide y se reinstala solo."""
    if not MARKER.exists():
        return False
    try:
        return MARKER.read_text(encoding="utf-8").strip() == hash_requirements()
    except Exception:
        return False


def entorno_importable(py: Path) -> bool:
    """Comprueba imports reales del entorno, no solo el hash de requirements.

    Una carpeta .venv copiada o una instalación nativa incompleta puede tener
    el marcador correcto y aun así fallar recién al transcribir. Esta prueba
    no abre la interfaz ni descarga modelos.
    """
    try:
        codigo = "import " + ", ".join(MODULOS_REQUERIDOS)
        return subprocess.run([str(py), "-c", codigo], check=False).returncode == 0
    except OSError:
        return False


def instalar_deps(py: Path):
    print("[2/2] Instalando dependencias (requiere internet la primera vez o "
          "cuando se agregan nuevas)...")
    try:
        subprocess.check_call([str(py), "-m", "pip", "install", "--upgrade", "pip"])
        subprocess.check_call([str(py), "-m", "pip", "install", "--upgrade", "-r", str(REQS)])
    except subprocess.CalledProcessError as e:
        print(f"\nError instalando dependencias: {e}")
        print("Revisa tu conexion a internet y vuelve a ejecutar 'python run.py'.")
        sys.exit(1)
    if not entorno_importable(py):
        print("\nLas dependencias se instalaron, pero una no se puede importar.")
        print("Revisa el detalle anterior y ejecuta de nuevo: python run.py --update")
        sys.exit(1)
    MARKER.write_text(hash_requirements(), encoding="utf-8")


def main():
    if sys.version_info < (3, 8):
        print("Se necesita Python 3.8 o superior. Version actual:",
              ".".join(map(str, sys.version_info[:3])))
        sys.exit(1)

    if not APP.exists():
        print(f"No se encontro la app: {APP}")
        sys.exit(1)

    py = venv_python(VENV_DIR)
    forzar = "--update" in sys.argv or "--repair" in sys.argv

    if not py.exists():
        crear_venv()
        py = venv_python(VENV_DIR)

    if forzar or not deps_al_dia() or not entorno_importable(py):
        instalar_deps(py)

    # Lanza la interfaz grafica con el Python del entorno virtual.
    # En Windows os.execv puede construir mal la línea de comandos cuando la
    # ruta contiene espacios o paréntesis (p. ej. una carpeta de Descargas
    # terminada en "(4)"). subprocess recibe los argumentos por separado y
    # conserva esas rutas sin reinterpretarlas.
    print("Abriendo el Transcriptor Whisper...")
    try:
        raise SystemExit(subprocess.call([str(py), str(APP)]))
    except OSError:
        print("\nNo se pudo abrir la aplicación con el entorno instalado.")
        print(f"Intenta ejecutar manualmente:\n    {py} {APP}")
        sys.exit(1)


if __name__ == "__main__":
    main()
