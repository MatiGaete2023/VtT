"""Pruebas del escritorio. No requieren faster-whisper/sounddevice/soundcard
instalados: transcriptor_whisper.py los importa de forma perezosa (dentro de
funciones), nunca a nivel de modulo, asi que este archivo tampoco los necesita.
"""
import array
import hashlib
import importlib.util
import math
import queue
import sys
import threading
import wave
from pathlib import Path
from types import SimpleNamespace

DESKTOP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DESKTOP_DIR))

import transcriptor_whisper as tw  # noqa: E402


# ---------- envolver_texto (ajuste de lineas del .txt/.md) ----------

def test_envolver_texto_respeta_ancho():
    texto = "palabra " * 40
    resultado = tw.envolver_texto(texto, ancho=100)
    for linea in resultado.splitlines():
        assert len(linea) <= 100


def test_envolver_texto_preserva_parrafos():
    texto = "primer parrafo\n\nsegundo parrafo"
    resultado = tw.envolver_texto(texto, ancho=100)
    assert "primer parrafo" in resultado
    assert "segundo parrafo" in resultado
    assert resultado.count("\n\n") >= 1


def test_envolver_texto_sin_ajuste():
    texto = "x" * 500
    assert tw.envolver_texto(texto, ancho=0) == texto


# ---------- hilo escritor de grabacion (writer thread) ----------
# Reproduce, sin microfono real, la tuberia callback -> cola -> hilo escritor
# que graba el audio a disco. `_writer_grab` solo toca self.cola_grab,
# self.grab_stop, self.grab_descarta y self.wave_file, asi que se puede
# probar con un objeto liviano en vez de instanciar la app de Tk completa.

def test_writer_grab_produce_wav_correcto(tmp_path):
    rate = 16000
    ruta = tmp_path / "test.wav"
    wf = wave.open(str(ruta), "wb")
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(rate)

    descarte_esperado = int(rate * 0.12)
    fake = SimpleNamespace(
        cola_grab=queue.Queue(),
        grab_stop=threading.Event(),
        grab_descarta=descarte_esperado,
        wave_file=wf,
    )

    hilo = threading.Thread(target=tw.TranscriptorApp._writer_grab, args=(fake,))
    hilo.start()

    amp, freq, total, bloque = 8000, 220, rate, 512
    muestras = array.array("h", (
        int(amp * math.sin(2 * math.pi * freq * i / rate)) for i in range(total)
    ))
    for i in range(0, total, bloque):
        fake.cola_grab.put(muestras[i:i + bloque].tobytes())

    fake.grab_stop.set()
    fake.cola_grab.put(None)
    hilo.join(timeout=2)
    wf.close()

    w = wave.open(str(ruta), "rb")
    assert w.getframerate() == rate
    assert w.getnchannels() == 1
    leidas = array.array("h")
    leidas.frombytes(w.readframes(w.getnframes()))
    assert len(leidas) > 0

    rms = math.sqrt(sum(x * x for x in leidas) / len(leidas))
    assert 5000 < rms < 6200  # esperado ~5657 para amplitud 8000

    descartadas = total - w.getnframes()
    assert descartadas == descarte_esperado  # se descarto el pop de arranque


# ---------- hash de requirements.txt (run.py) ----------

def _cargar_run_module():
    spec = importlib.util.spec_from_file_location("run_mod", DESKTOP_DIR / "run.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_hash_requirements_detecta_falta_e_igualdad_y_cambio(tmp_path):
    run_mod = _cargar_run_module()
    reqs = tmp_path / "requirements.txt"
    reqs.write_text("faster-whisper>=1.0.0\n")
    venv_dir = tmp_path / ".venv"
    venv_dir.mkdir()
    marker = venv_dir / ".deps_ok"

    run_mod.REQS = reqs
    run_mod.MARKER = marker

    # Sin marcador -> hace falta instalar.
    assert run_mod.deps_al_dia() is False

    # Marcador con el hash correcto -> no hace falta instalar.
    marker.write_text(run_mod.hash_requirements(), encoding="utf-8")
    assert run_mod.deps_al_dia() is True

    # requirements.txt cambio (nueva dependencia) -> hace falta reinstalar.
    reqs.write_text("faster-whisper>=1.0.0\nsoundcard>=0.4.2\n")
    assert run_mod.deps_al_dia() is False


def test_hash_requirements_es_sha256():
    run_mod = _cargar_run_module()
    esperado = hashlib.sha256(run_mod.REQS.read_bytes()).hexdigest()
    assert run_mod.hash_requirements() == esperado


# ---------- rutas persistentes (grabaciones/transcripciones nunca en temporales) ----------

def test_es_temporal_true_dentro_de_carpeta_temp(tmp_path):
    fake = SimpleNamespace(temp_dirs=[str(tmp_path)])
    archivo = tmp_path / "descarga.mp3"
    archivo.write_bytes(b"")
    assert tw.TranscriptorApp._es_temporal(fake, str(archivo)) is True


def test_es_temporal_false_para_archivo_fuera_de_temp(tmp_path):
    otro = tmp_path / "otro_dir"
    otro.mkdir()
    fake = SimpleNamespace(temp_dirs=[str(otro)])
    archivo = tmp_path / "normal.mp3"
    archivo.write_bytes(b"")
    assert tw.TranscriptorApp._es_temporal(fake, str(archivo)) is False


def test_es_temporal_false_sin_temp_dirs(tmp_path):
    fake = SimpleNamespace(temp_dirs=[])
    archivo = tmp_path / "normal.mp3"
    archivo.write_bytes(b"")
    assert tw.TranscriptorApp._es_temporal(fake, str(archivo)) is False


def test_carpetas_persistentes_existen():
    assert tw.CARPETA_GRABACIONES.is_dir()
    assert tw.CARPETA_TRANSCRIPCIONES.is_dir()


# ---------- historial de carpetas de salida ----------

def test_registrar_salida_dedupe_y_orden():
    fake = SimpleNamespace(historial_salidas=[], _snapshot_config=lambda: None)
    tw.TranscriptorApp._registrar_salida(fake, "/a")
    tw.TranscriptorApp._registrar_salida(fake, "/b")
    tw.TranscriptorApp._registrar_salida(fake, "/a")  # ya estaba: vuelve al frente
    assert fake.historial_salidas == ["/a", "/b"]


def test_registrar_salida_tope_10():
    fake = SimpleNamespace(historial_salidas=[], _snapshot_config=lambda: None)
    for i in range(15):
        tw.TranscriptorApp._registrar_salida(fake, f"/carpeta{i}")
    assert len(fake.historial_salidas) == 10
    assert fake.historial_salidas[0] == "/carpeta14"  # la mas reciente va primero
