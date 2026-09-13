import queue
import threading

import vtt_performance as performance
from vtt_pipeline_ultra import PipelineUltraMixin, ultra_speaker_counts
from vtt_ultra_config import (
    ULTRA_AUTO_THRESHOLD,
    ULTRA_DIAR_PROFILE,
    ULTRA_PROFILE_NAME,
    ULTRA_QUALITY_PROFILE_NAME,
    ULTRA_QUALITY_TARGET_PROCESSING_RATIO,
    ULTRA_WINDOW_SHIFT_RATIO,
    install_ultra_mode,
    is_ultra_quality,
    ultra_threshold_for_speaker_mode,
    ultra_word_timestamps,
)
import vtt_diarization_v4 as diar4


install_ultra_mode()


def test_ultra_profiles_are_installed_with_different_quality_budgets():
    fast = performance.global_profile(ULTRA_PROFILE_NAME)
    assert fast["model"] == "tiny"
    assert fast["asr_profile"] == "Rapido"
    assert fast["diarize"] is True
    assert fast["speaker_mode"] == "Auto"
    assert fast["diar_profile"] == ULTRA_DIAR_PROFILE
    assert fast["target_processing_ratio"] == 0.60

    quality = performance.global_profile(ULTRA_QUALITY_PROFILE_NAME)
    assert quality["model"] == "base"
    assert quality["asr_profile"] == "Rapido"
    assert quality["diarize"] is True
    assert quality["speaker_mode"] == "Auto"
    assert quality["diar_profile"] == ULTRA_DIAR_PROFILE
    assert quality["target_processing_ratio"] == ULTRA_QUALITY_TARGET_PROCESSING_RATIO == 0.22
    assert is_ultra_quality(ULTRA_QUALITY_PROFILE_NAME) is True
    assert is_ultra_quality(ULTRA_PROFILE_NAME) is False
    assert diar4.DIARIZATION_PROFILES[ULTRA_DIAR_PROFILE]["window_shift_ratio"] == ULTRA_WINDOW_SHIFT_RATIO


def test_ultra_quality_forces_word_timestamps_but_max_speed_does_not():
    assert ultra_word_timestamps(False, ULTRA_PROFILE_NAME) is False
    assert ultra_word_timestamps(True, ULTRA_PROFILE_NAME) is True
    assert ultra_word_timestamps(False, ULTRA_QUALITY_PROFILE_NAME) is True


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
            "raw_sherpa_ids": [0, 1],
            "raw_sherpa_selected_speakers": 2,
            "detected_speakers_before_identity": 2,
            "detected_speakers": 2,
            "identity_verification": {
                "enabled": bool(kwargs.get("identity_lite")),
                "mode": "ultra_lite" if kwargs.get("identity_lite") else None,
            },
        }


class _DummyUltra(PipelineUltraMixin):
    def __init__(self, profile_name=ULTRA_PROFILE_NAME):
        self.cancelar = threading.Event()
        self._cola_diar_ui = queue.Queue()
        self._diar_profile_run = ULTRA_DIAR_PROFILE
        self._global_profile_run = profile_name
        self._v5_user_words_run = False
        self._v5_forced_words_run = profile_name == ULTRA_QUALITY_PROFILE_NAME
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
    assert app.service.kwargs["identity_lite"] is False
    assert app.service.kwargs["threshold"] == 0.82
    assert app.service.kwargs["diar_profile"] == ULTRA_DIAR_PROFILE
    assert meta["passes"] == 1
    assert meta["retry"] is False
    assert meta["retry_requested"] is False
    assert meta["retry_avoided"] is False
    assert meta["selection_reason"] == "ultra_una_pasada"
    assert meta["identity_verification"]["enabled"] is False
    assert meta["alignment"]["mode"] == "segment_overlap"
    assert meta["word_timestamps_forced_for_diarization"] is False
    assert meta["speaker_count_validation"]["status"] == "estimacion_ultra_una_pasada"
    assert meta["speaker_count_validation"]["ambiguous"] is True
    assert len(out) == 2
    assert len(speakers) == 2


def test_ultra_quality_uses_word_alignment_and_identity_lite():
    app = _DummyUltra(ULTRA_QUALITY_PROFILE_NAME)
    segs = [{
        "start": 0.0,
        "end": 4.0,
        "text": "hola mundo otra voz final",
        "words": [
            {"start": 0.0, "end": 0.8, "word": " hola"},
            {"start": 0.8, "end": 1.8, "word": " mundo"},
            {"start": 2.1, "end": 2.9, "word": " otra"},
            {"start": 2.9, "end": 3.8, "word": " voz"},
            {"start": 3.8, "end": 4.0, "word": " final"},
        ],
    }]
    out, speakers, meta = app._diarizar_pipeline(
        "fake.wav", segs, 4.0,
        {"num_speakers": "Auto"},
        lambda _msg: None,
    )
    assert app.service.kwargs["adaptive"] is False
    assert app.service.kwargs["identity_lite"] is True
    assert meta["passes"] == 1
    assert meta["selection_reason"] == "ultra_calidad_una_pasada"
    assert meta["ultra_quality_mode"] is True
    assert meta["identity_verification"]["enabled"] is True
    assert meta["alignment"]["mode"] == "word_level"
    assert meta["alignment"]["speaker_switches_inside_segments"] >= 1
    assert meta["word_timestamps_forced_for_diarization"] is True
    assert meta["speaker_count_validation"]["status"] == "estimacion_ultra_calidad_una_pasada"
    assert len(out) >= 2
    assert len(speakers) == 2
    # Las palabras fueron de uso interno: no se exportan si el usuario no las pidió.
    assert all(s.get("words") == [] for s in out)
