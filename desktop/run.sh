#!/usr/bin/env bash
# Lanzador para macOS y Linux. Abre el Transcriptor Whisper.
# Solo necesita tener Python 3 instalado.
set -e
cd "$(dirname "$0")"

if command -v python3 >/dev/null 2>&1; then
    PY=python3
elif command -v python >/dev/null 2>&1; then
    PY=python
else
    echo "No se encontro Python. Instala Python 3.8 o superior:"
    echo "  macOS:  brew install python-tk    (o https://www.python.org/downloads/)"
    echo "  Linux:  sudo apt install python3 python3-venv python3-tk"
    exit 1
fi

exec "$PY" run.py "$@"
