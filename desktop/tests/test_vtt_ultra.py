import queue
import threading

import vtt_performance as performance
from vtt_pipeline_ultra import PipelineUltraMixin, ultra_speaker_counts
from vtt_ultra_config import (
    ULTRA_AUTO_THRESHOLD,
    ULTRA_DIAR_PROFILE,
    ULTRA_PROFILE_NAME,
    ULTRA_WINDOW_SHIFT_RATIO,
    install_ultra_mode,
    ultra_threshold_for_speaker_mode,
    ultra_word_timestamps,
)
import vtt_diarization_v4 as diar4


install_ultra_mode()


def test_ultra_profile_is_installed_and_prefers_speed():
    p = performance.global_profile(ULTRA_PROFILE_NAME)
    assert p["model"] == "tiny"
    assert p["asr_profile"] == "Rapido"
    assert p["diarize"] is True
    assert p["speaker_mode"] == "Auto"
    assert p["diar_profile"] == ULTRA_DIAR_PROFILE
    assert p["target_processing_ratio"] == 0.60
    assert diar4.DIARIZATION_PROFILES[ULTRA_DIAR_PROFILE]["window_shift_ratio"] == ULTRA_WINDOW_SHIFT_RATIO


def test_ultra_does_not_force_word_timestamps():
    assert ultra_word_timestamps(False) is False
    assert ultra_word_timestamps(True) is True


def test_ultra_auto_uses_single_merge_oriented_threshold():
    assert ultra_threshold_for_speaker_mode("Auto") == ULTRA_AUTO_THRESHOLD == 0.82
    assert ultra_threshold_for_speaker_mode("3") == 0.5


def test_ultra_counts_keep_acoustic_clusters_without_text():
    turns = [
        {"start": 0.0, "end": 1.0, "speaker": 0},
        {"start": 1.0, "end": 2.0, "speaker": 1},
        {"start": 2.0, "end": 3.0, "speaker": 2},
    ]
    speakers = [
        {"raw_numeric_id": 0, "display_name": "Persona 1"},
        {"raw_numeric_id": 2, "display_name": "Persona 2"},
    ]
    counts = ultra_speaker_counts(turns, speakers)
    assert counts["raw_acoustic_clusters"] == 3
    assert counts["identity_clusters_after_refinement"] == 3
    assert counts["text_assigned_speakers"] == 2
    assert counts["unassigned_raw_ids"] == [1]


class _FakeService:
    def __init__(self):
        self.kwargs = None

    def diarize(self, _archivo, **kwargs):
        self.kwargs = kwargs
        return [
            {"start": 0.0, "end": 2.0, "speaker": 0},
            {"start": 2.0, "end": 4.0, "speaker": 1},
        ], {
            "selected_analysis": {"speaker_count": 2, "penalty": 0.0},
            "sherpa_internal_timing_available": False,
            "sherpa_internal": {},
            "sherpa_process_wall_seconds": 1.0,
            "num_threads": 2,
            "diarization_profile": ULTRA_DIAR_PROFILE,
            "window_shift_ratio": ULTRA_WINDOW_SHIFT_RATIO,
            "candidates": [],
        }


class _DummyUltra(PipelineUltraMixin):
    def __init__(self):
        self.cancelar = threading.Event()
        self._cola_diar_ui = queue.Queue()
        self._diar_profile_run = ULTRA_DIAR_PROFILE
        self.service = _FakeService()

    def _diar_service(self):
        return self.service

    def _emitir_progreso_diarizacion(self, *_args):
        pass


def test_ultra_pipeline_calls_sherpa_once_without_adaptive_retry():
    app = _DummyUltra()
    segs = [
        {"start": 0.0, "end": 2.0, "text": "hola", "words": []},
        {"start": 2.0, "end": 4.0, "text": "mundo", "words": []},
    ]
    out, speakers, meta = app._diarizar_pipeline(
        "fake.wav", segs, 4.0,
        {"num_speakers": "Auto"},
        lambda _msg: None,
    )
    assert app.service.kwargs["adaptive"] is False
    assert app.service.kwargs["threshold"] == 0.82
    assert app.service.kwargs["diar_profile"] == ULTRA_DIAR_PROFILE
    assert meta["passes"] == 1
    assert meta["retry"] is False
    assert meta["identity_verification"]["enabled"] is False
    assert meta["alignment"]["mode"] == "segment_overlap"
    assert meta["word_timestamps_forced_for_diarization"] is False
    assert len(out) == 2
    assert len(speakers) == 2
