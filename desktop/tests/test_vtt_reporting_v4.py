from docx import Document

import vtt_reporting_v4 as r4


def _metricas():
    return {
        "audio_seconds": 120.0,
        "asr_seconds": 30.0,
        "diarization_seconds": 40.0,
        "export_seconds": 1.0,
        "overhead_seconds": 0.0,
        "model_load_seconds": 5.0,
        "device": "cpu",
        "compute_type": "int8",
        "batched": True,
        "batch_size": 4,
        "beam_size": 5,
        "diarization_enabled": True,
        "speaker_mode": "Auto",
        "speaker_detected": 4,
        "diarization_threads": 4,
        "auto_threshold": 0.68,
        "diarization_profile": "Equilibrada",
        "window_shift_ratio": 0.20,
        "auto_passes": 2,
        "auto_selection_reason": "segunda_pasada_mejora_estructura",
        "auto_retry_reason": "tramo_monopolizado",
        "auto_stability_delta_speakers": 1,
        "auto_selected_analysis": {"speaker_count": 4, "penalty": 0.2},
        "auto_candidates": [
            {"threshold": 0.74, "analysis": {"speaker_count": 3, "penalty": 1.2}},
            {"threshold": 0.68, "analysis": {"speaker_count": 4, "penalty": 0.2}},
        ],
    }


def test_json_v4_incluye_diagnostico_diarizacion():
    doc = r4.documento_json_detallado(
        "a.wav", "small", "es", "hola",
        [{"start": 0, "end": 1, "text": "hola", "speaker": "Persona 1"}],
        [{"start": 0, "end": 1, "text": "hola", "speaker": "Persona 1"}],
        [{"display_name": "Persona 1"}],
        _metricas(), "Preciso", "",
    )
    assert doc["schema_version"] >= 4
    assert doc["configuration"]["diarization_profile"] == "Equilibrada"
    assert doc["diarization"]["passes"] == 2
    assert len(doc["diarization"]["candidates"]) == 2


def test_docx_v4_muestra_perfil_y_seleccion(tmp_path):
    ruta = tmp_path / "x.docx"
    r4.escribir_docx_detallado(
        ruta, "a.wav", "small", "es",
        [{"start": 0, "text": "hola", "speaker": "Persona 1"}],
        _metricas(), "Preciso",
    )
    doc = Document(ruta)
    tabla = doc.tables[0]
    pares = {row.cells[0].text: row.cells[1].text for row in tabla.rows}
    assert pares["Perfil diarización"] == "Equilibrada"
    assert pares["Window shift"] == "0.20"
    assert pares["Pasadas Auto"] == "2"
