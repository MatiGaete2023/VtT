from pathlib import Path

import vtt_alignment as alignment
import vtt_diarization_v5 as diar5
import vtt_validation as validation


def _w(start, end, text):
    return {"start": start, "end": end, "word": text, "probability": 0.9}


def test_divide_segmento_cuando_cambia_hablante_por_palabra():
    segmentos = [{
        "id": 7,
        "start": 0.0,
        "end": 4.0,
        "text": "Hola mundo Cambio voz",
        "words": [
            _w(0.0, 0.8, " Hola"),
            _w(0.8, 1.6, " mundo"),
            _w(2.0, 2.8, " Cambio"),
            _w(2.8, 3.6, " voz"),
        ],
        "avg_logprob": -0.2,
    }]
    turnos = [
        {"start": 0.0, "end": 1.8, "speaker": 5},
        {"start": 1.9, "end": 4.0, "speaker": 9},
    ]
    out, meta = alignment.alinear_y_dividir(segmentos, turnos)
    assert len(out) == 2
    assert [x["speaker_id"] for x in out] == [5, 9]
    assert [x["text"] for x in out] == ["Hola mundo", "Cambio voz"]
    assert [x["source_segment_id"] for x in out] == [7, 7]
    assert meta["split_source_segments"] == 1
    assert meta["speaker_switches_inside_segments"] == 1
    assert meta["assigned_words"] == 4


def test_flip_de_una_palabra_entre_mismo_hablante_se_suaviza():
    segmentos = [{
        "id": 1,
        "start": 0.0,
        "end": 3.0,
        "text": "uno dos tres",
        "words": [
            _w(0.0, 0.8, " uno"),
            _w(0.9, 1.1, " dos"),
            _w(1.2, 2.0, " tres"),
        ],
    }]
    turnos = [
        {"start": 0.0, "end": 0.85, "speaker": 0},
        {"start": 0.85, "end": 1.15, "speaker": 1},
        {"start": 1.15, "end": 2.2, "speaker": 0},
    ]
    out, meta = alignment.alinear_y_dividir(segmentos, turnos)
    assert len(out) == 1
    assert out[0]["speaker_id"] == 0
    assert meta["speaker_switches_inside_segments"] == 0


def test_sin_palabras_conserva_fallback_por_segmento():
    out, meta = alignment.alinear_y_dividir(
        [{"id": 0, "start": 0.0, "end": 2.0, "text": "hola", "words": []}],
        [{"start": 0.0, "end": 2.0, "speaker": 3}],
    )
    assert len(out) == 1
    assert out[0]["speaker_id"] == 3
    assert meta["fallback_segments"] == 1


def test_parsea_timers_internos_sherpa():
    log = """
x OfflineSpeakerDiarization: segmentation 1.250 s
x OfflineSpeakerDiarization: embedding 2.500 s
x OfflineSpeakerDiarization: clustering 0.125 s
x OfflineSpeakerDiarization: total 3.900 s, audio 10.000 s, RTF 0.390
"""
    m = diar5.parse_sherpa_timings(log)
    assert m["segmentation_seconds"] == 1.25
    assert m["embedding_seconds"] == 2.5
    assert m["clustering_seconds"] == 0.125
    assert m["sherpa_total_seconds"] == 3.9
    assert m["sherpa_rtf"] == 0.39


def test_motor_reutiliza_sesion_si_shift_no_cambia(monkeypatch):
    class Cfg:
        def validate(self):
            return True

    class FakeSD:
        def __init__(self, cfg):
            self.cfg = cfg
            self.set_calls = 0
        def set_config(self, cfg):
            self.cfg = cfg
            self.set_calls += 1

    class FakeSherpa:
        OfflineSpeakerDiarization = FakeSD

    monkeypatch.setattr(diar5, "_config", lambda *a, **k: Cfg())
    e = diar5.DiarizationEngine(Path("."))
    e.sherpa = FakeSherpa
    e.seg_model = Path("seg.onnx")
    e.emb_model = Path("emb.onnx")
    e.threads = 4

    sd1, m1 = e._engine(num_speakers=-1, threshold=0.74, shift=0.20)
    sd2, m2 = e._engine(num_speakers=-1, threshold=0.68, shift=0.20)
    assert sd1 is sd2
    assert m1["engine_reused"] is False
    assert m2["engine_reused"] is True
    assert sd1.set_calls == 1


def test_cambio_de_shift_reinicializa_motor(monkeypatch):
    class Cfg:
        def validate(self):
            return True
    class FakeSD:
        def __init__(self, cfg):
            pass
        def set_config(self, cfg):
            raise AssertionError("no debe reutilizar con shift distinto")
    class FakeSherpa:
        OfflineSpeakerDiarization = FakeSD
    monkeypatch.setattr(diar5, "_config", lambda *a, **k: Cfg())
    e = diar5.DiarizationEngine(Path("."))
    e.sherpa = FakeSherpa
    e.seg_model = Path("seg.onnx")
    e.emb_model = Path("emb.onnx")
    e.threads = 4
    sd1, _ = e._engine(num_speakers=-1, threshold=0.74, shift=0.20)
    sd2, m2 = e._engine(num_speakers=-1, threshold=0.74, shift=0.25)
    assert sd1 is not sd2
    assert m2["engine_reused"] is False


def test_conteo_auto_estable_no_se_presenta_como_ground_truth():
    meta = {"selected_analysis": {"penalty": 0.4}, "retry": False}
    out = validation.evaluar_conteo_hablantes(meta, 5)
    assert out["status"] == "estimacion_acustica_estable"
    assert out["estimated_speakers"] == 5
    assert out["ground_truth_available"] is False
    assert out["ground_truth_speakers"] is None


def test_conteo_inestable_se_marca():
    meta = {
        "selected_analysis": {"penalty": 0.5},
        "retry": True,
        "stability_delta_speakers": 5,
    }
    out = validation.evaluar_conteo_hablantes(meta, 4)
    assert out["status"] == "estimacion_inestable"


def test_modo_manual_declara_que_el_conteo_fue_fijado():
    out = validation.evaluar_conteo_hablantes({}, 4, manual_requested=4)
    assert out["status"] == "conteo_fijado_por_usuario"
