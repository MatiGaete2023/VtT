from docx import Document

import vtt_reporting as reporting


def test_metricas_por_etapa_recalculan_total():
    m = reporting.cerrar_metricas({
        "audio_seconds": 100,
        "asr_seconds": 20,
        "diarization_seconds": 30,
        "export_seconds": 5,
        "overhead_seconds": 1,
    })
    assert m["processing_seconds"] == 56
    assert m["speed_x"] == 100 / 56


def test_json_detallado_incluye_configuracion_y_diarizacion():
    m = reporting.cerrar_metricas({
        "audio_seconds": 100,
        "asr_seconds": 20,
        "diarization_seconds": 30,
        "export_seconds": 5,
        "diarization_enabled": True,
        "speaker_mode": "Auto",
        "speaker_detected": 3,
        "device": "cpu",
        "compute_type": "int8",
        "batched": True,
        "batch_size": 4,
        "beam_size": 5,
    })
    doc = reporting.documento_json_detallado(
        "a.wav", "small", "es", "hola", [], [], [], m, "Preciso", ""
    )
    assert doc["schema_version"] == 3
    assert doc["configuration"]["batch_size"] == 4
    assert doc["diarization"]["detected_speakers"] == 3
    assert doc["timing"]["asr_seconds"] == 20


def test_docx_detallado_muestra_tiempos(tmp_path):
    path = tmp_path / "out.docx"
    m = reporting.cerrar_metricas({
        "audio_seconds": 100,
        "asr_seconds": 20,
        "diarization_seconds": 30,
        "export_seconds": 5,
        "diarization_enabled": True,
        "speaker_mode": "Auto",
        "speaker_detected": 3,
        "device": "cpu",
        "compute_type": "int8",
        "batched": True,
        "batch_size": 4,
        "beam_size": 5,
    })
    reporting.escribir_docx_detallado(
        path, "a.wav", "small", "es",
        [{"start": 0, "speaker": "Persona 1", "text": "Hola"}],
        m, "Preciso",
    )
    doc = Document(path)
    tabla = doc.tables[0]
    datos = {row.cells[0].text: row.cells[1].text for row in tabla.rows}
    assert "Transcripción ASR" in datos
    assert "Identificación hablantes" in datos
    assert datos["Hablantes"].startswith("Auto")
