import hashlib

import vtt_diarization as diar


def test_validar_modelo_prefiere_hash_de_origen_sobre_sidecar(tmp_path):
    p = tmp_path / "model.onnx"
    p.write_bytes(b"contenido-auditado")
    good = hashlib.sha256(p.read_bytes()).hexdigest()
    # Un sidecar TOFU falso no puede imponerse sobre el valor de origen fijado.
    p.with_suffix(p.suffix + ".sha256").write_text("0" * 64, encoding="utf-8")
    ok, reason = diar.validar_archivo_modelo(
        p, len(p.read_bytes()), sha256_esperado=good
    )
    assert ok is True
    assert reason == "ok"
    assert p.with_suffix(p.suffix + ".sha256").read_text().strip() == good


def test_validar_modelo_rechaza_hash_distinto_aunque_tamano_coincida(tmp_path):
    p = tmp_path / "model.onnx"
    p.write_bytes(b"mismo-tamano")
    p.with_suffix(p.suffix + ".sha256").write_text(
        hashlib.sha256(p.read_bytes()).hexdigest(), encoding="utf-8"
    )
    ok, reason = diar.validar_archivo_modelo(
        p, len(p.read_bytes()), sha256_esperado="f" * 64
    )
    assert ok is False
    assert "auditado" in reason


def test_catalogo_diarizacion_tiene_hashes_sha256_completos():
    values = (
        diar.SEGMENTATION_ARCHIVE_SHA256,
        diar.SEGMENTATION_MODEL_SHA256,
        diar.EMBEDDING_SHA256,
    )
    assert all(len(x) == 64 for x in values)
    assert all(set(x) <= set("0123456789abcdef") for x in values)
