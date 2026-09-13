import json
import queue
import threading
from pathlib import Path

import pytest
from docx import Document
from docx.document import Document as DocumentClass

import transcriptor_whisper as base
import vtt_diarization_service as service5
import vtt_diarization_service_v51 as service51
import vtt_diarization_service_v52 as service52
from vtt_diarization_errors import DiarizacionCancelada
import vtt_diarization_v52 as diar52
import vtt_performance as performance
import vtt_pipeline as pipeline3
import vtt_pipeline_v5 as pipeline5
import vtt_pipeline_v52 as pipeline52
import vtt_reporting as reporting
import vtt_reporting_v52 as reporting52


def test_all_persistent_services_share_one_cancellation_exception():
    assert service5.DiarizacionCancelada is DiarizacionCancelada
    assert service51.DiarizacionCancelada is DiarizacionCancelada
    assert service52.DiarizacionCancelada is DiarizacionCancelada


def test_pipeline_v5_translates_active_service_cancellation(monkeypatch):
    class FakeService:
        def diarize(self, *args, **kwargs):
            raise DiarizacionCancelada()

    class Dummy:
        _diar_profile_run = "Equilibrada"
        _v5_user_words_run = False
        _v5_forced_words_run = False
        cancelar = threading.Event()
        _cola_diar_ui = queue.SimpleQueue()

        def _diar_service(self):
            return FakeService()

        def _emitir_progreso_diarizacion(self, *args, **kwargs):
            pass

    monkeypatch.setattr(
        pipeline5.tuning,
        "regiones_voz_desde_segmentos",
        lambda _segs, _dur: ([], {"enabled": False, "reason": "test"}),
    )
    with pytest.raises(base.Cancelado):
        pipeline5.PipelineV5Mixin._diarizar_pipeline(
            Dummy(), "dummy.wav",
            [{"start": 0.0, "end": 1.0, "text": "hola", "words": []}],
            1.0, {"num_speakers": "Auto"}, lambda _x: None,
        )


def test_asr_checkpoint_is_recoverable_and_atomic(tmp_path):
    obj = object.__new__(pipeline3.PipelineV3Mixin)
    path = obj._guardar_checkpoint_asr(
        tmp_path, "audio.webm", "small", "es", "hola mundo",
        [{"start": 0.0, "end": 1.0, "text": "hola mundo"}], 2.5,
    )
    assert path.exists()
    assert not path.with_suffix(path.suffix + ".tmp").exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["schema"] == "vtt_asr_checkpoint_v1"
    assert data["text"] == "hola mundo"
    assert data["asr_seconds"] == 2.5
    obj._quitar_checkpoint_asr(path)
    assert not path.exists()


def test_speaker_snapshot_reproduces_8_10_9_raw5_without_collapsing_counts():
    meta = {
        "raw_sherpa_selected_speakers": 8,
        "detected_speakers_engine": 9,
        "identity_consistency": {
            "speakers": [
                {"speaker": x} for x in (0, 1, 2, 3, 4, 5, 6, 7, 8, 10)
            ]
        },
    }
    speakers = [
        {"raw_numeric_id": x, "display_name": f"Persona {i + 1}"}
        for i, x in enumerate((0, 1, 2, 3, 4, 6, 7, 8, 10))
    ]
    counts = pipeline52.speaker_count_snapshot(meta, speakers)
    assert counts["raw_acoustic_clusters"] == 8
    assert counts["engine_identity_clusters"] == 9
    assert counts["identity_consistency_clusters"] == 10
    assert counts["identity_clusters_after_refinement"] == 10
    assert counts["text_assigned_speakers"] == 9
    assert counts["unassigned_raw_ids"] == [5]
    assert counts["identity_count_mismatch"] is True


def test_final_metrics_include_report_and_end_to_end():
    m = reporting.cerrar_metricas({
        "audio_seconds": 10,
        "model_load_seconds": 2,
        "asr_seconds": 5,
        "diarization_seconds": 3,
        "export_seconds": 1,
        "overhead_seconds": 1,
        "report_generation_seconds": 2,
    })
    assert m["processing_seconds"] == 10
    assert m["end_to_end_seconds"] == 14
    assert m["speed_x"] == 1.0


def test_json_recalculates_performance_instead_of_preserving_stale_state():
    metrics = reporting.cerrar_metricas({
        "audio_seconds": 10,
        "asr_seconds": 8,
        "diarization_seconds": 3,
        "export_seconds": 1,
        "overhead_seconds": 1,
        "model_load_seconds": 0,
        "report_generation_seconds": 0,
        "diarization_enabled": False,
        "speaker_mode": "No",
        "device": "cpu",
        "compute_type": "int8",
        "batched": True,
        "batch_size": 8,
        "beam_size": 5,
    })
    metrics["performance"] = {"within_realtime": True, "processing_to_audio": 0.9}
    doc = reporting52.documento_json_detallado(
        "a.wav", "small", "es", "hola", [], [], [], metrics,
        "Equilibrado", "",
    )
    assert doc["performance"]["within_realtime"] is False
    assert doc["performance"]["processing_to_audio"] == pytest.approx(1.3)


def test_v52_docx_is_saved_once(tmp_path, monkeypatch):
    count = {"n": 0}
    original = DocumentClass.save

    def counted(self, path_or_stream):
        count["n"] += 1
        return original(self, path_or_stream)

    monkeypatch.setattr(DocumentClass, "save", counted)
    path = tmp_path / "single-save.docx"
    reporting52.escribir_docx_detallado(
        path, "audio.wav", "small", "es",
        [{"start": 0.0, "speaker": None, "text": "Hola"}],
        {
            "audio_seconds": 10.0,
            "asr_seconds": 2.0,
            "diarization_seconds": 0.0,
            "export_seconds": 0.1,
            "report_generation_seconds": 0.0,
            "overhead_seconds": 0.0,
            "diarization_enabled": False,
            "speaker_mode": "No",
            "speaker_detected": 0,
            "device": "cpu",
            "compute_type": "int8",
            "batched": True,
            "batch_size": 8,
            "beam_size": 5,
        },
        "Equilibrado",
    )
    assert path.exists()
    assert count["n"] == 1
    assert Document(path).paragraphs


def test_global_presets_enable_auto_and_precise_uses_balanced_diarization():
    for name in ("Rápido", "Equilibrado", "Preciso"):
        cfg = performance.global_profile(name)
        assert cfg["diarize"] is True
        assert cfg["speaker_mode"] == "Auto"
    assert performance.global_profile("Preciso")["diar_profile"] == "Equilibrada"
    assert performance.infer_global_profile(
        "medium", "Preciso", "Precisa", diarize=True, speaker_mode="Auto"
    ) == "Personalizado"
    assert performance.infer_global_profile(
        "medium", "Preciso", "Equilibrada", diarize=True, speaker_mode="Auto"
    ) == "Preciso"


def test_balanced_budget_uses_remaining_realtime_window():
    budget = performance.diarization_budget_seconds(
        audio_seconds=404.0, asr_seconds=164.0,
        profile_name="Equilibrado", reserve_seconds=5.0,
    )
    assert budget == pytest.approx(235.0)
    assert performance.diarization_budget_seconds(
        audio_seconds=404.0, asr_seconds=164.0,
        profile_name="Personalizado", reserve_seconds=5.0,
    ) is None


def test_auto_skips_second_pass_when_projection_breaks_budget():
    limited = diar52.should_skip_retry_for_budget(
        time_budget_seconds=235,
        elapsed_seconds=120,
        first_pass_seconds=130,
        precheck_seconds=8,
    )
    assert limited["skip"] is True
    assert limited["projected_total_seconds"] == pytest.approx(258)

    enough = diar52.should_skip_retry_for_budget(
        time_budget_seconds=300,
        elapsed_seconds=120,
        first_pass_seconds=130,
        precheck_seconds=8,
    )
    assert enough["skip"] is False


def test_performance_status_reports_processing_and_end_to_end_separately():
    state = performance.performance_status({
        "audio_seconds": 100,
        "processing_seconds": 90,
        "end_to_end_seconds": 120,
        "asr_seconds": 60,
        "diarization_seconds": 30,
    })
    assert state["within_realtime"] is True
    assert state["end_to_end_within_realtime"] is False
    assert state["end_to_end_seconds_over_realtime"] == 20
