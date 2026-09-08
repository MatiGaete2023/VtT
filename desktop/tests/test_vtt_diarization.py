from pathlib import Path
import sys

DESKTOP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DESKTOP_DIR))

import vtt_diarization as vd


def test_sha_pin_detecta_alteracion(tmp_path):
    p = tmp_path / "modelo.onnx"
    p.write_bytes(b"modelo correcto")
    vd._guardar_hash_pin(p)
    ok, _ = vd.validar_archivo_modelo(p, len(b"modelo correcto"))
    assert ok is True
    p.write_bytes(b"modelo alterado")
    ok, motivo = vd.validar_archivo_modelo(p)
    assert ok is False
    assert "SHA-256" in motivo


def test_tamano_esperado_se_valida(tmp_path):
    p = tmp_path / "m.onnx"
    p.write_bytes(b"1234")
    ok, motivo = vd.validar_archivo_modelo(p, 10)
    assert ok is False
    assert "tamaño" in motivo


def test_urls_son_releases_oficiales_https():
    assert vd.SEGMENTATION_URL.startswith("https://github.com/k2-fsa/sherpa-onnx/releases/")
    assert vd.EMBEDDING_URL.startswith("https://github.com/k2-fsa/sherpa-onnx/releases/")
