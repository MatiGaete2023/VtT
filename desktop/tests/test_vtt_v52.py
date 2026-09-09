from pathlib import Path

import numpy as np

import vtt_diarization_v52 as diar52
import vtt_identity_v52 as identity52
import vtt_performance as performance
import vtt_reporting_v52 as reporting52
import vtt_validation_v52 as validation52


A = np.array([1.0, 0.0, 0.0], dtype=np.float32)
V = np.array([0.43, np.sqrt(1.0 - 0.43**2), 0.0], dtype=np.float32)


def test_two_turn_rival_aware_reassigns_conflict_above_old_threshold():
    turns = [
        {"start": 0, "end": 5, "speaker": 0},
        {"start": 20, "end": 25, "speaker": 0},
        {"start": 30, "end": 35, "speaker": 1},
        {"start": 40, "end": 45, "speaker": 1},
    ]
    out, meta = identity52.refinar_turnos(
        turns, {0: A, 1: V, 2: V, 3: V}, allow_new_identities=True
    )
    assert out[1]["speaker"] == 1
    assert any(
        x["reason"] == "two_turn_rival_explains_better"
        for x in meta["reassignments"]
    )


def test_two_turn_summary_uses_rival_signal():
    turns = [
        {"start": 0, "end": 5, "speaker": 0},
        {"start": 20, "end": 25, "speaker": 0},
        {"start": 30, "end": 35, "speaker": 1},
        {"start": 40, "end": 45, "speaker": 1},
    ]
    summary = identity52.resumir_identidades(
        turns, {0: A, 1: V, 2: V, 3: V}
    )
    sp0 = next(x for x in summary["speakers"] if x["speaker"] == 0)
    assert 0.42 < sp0["pair_similarity"] < 0.44
    assert sp0["rival_similarity_max"] > 0.99
    assert sp0["confidence"] == "baja"


def test_long_turn_probe_skips_detailed_scan_when_homogeneous():
    turns = [{"start": 0.0, "end": 30.0, "speaker": 0}]

    def cb(_a, _b):
        return A

    out, meta = identity52.escanear_cambios_locales(
        turns, cb, allow_new_identities=True, enabled=True
    )
    assert out == turns
    assert meta["probe_turns"] == 1
    assert meta["probe_skipped_turns"] == 1
    assert meta["detailed_scanned_turns"] == 0
    assert meta["applied_changes"] == 0


def test_one_embedding_report_does_not_show_trivial_one_point_similarity():
    text = reporting52._fmt_identity({
        "confidence": "insuficiente", "turns": 1, "embedded_turns": 1,
        "total_seconds": 4.0, "prototype_similarity_median": 1.0,
    })
    assert "1.00" not in text
    assert "muestra única" in text


def test_two_embedding_report_uses_pair_similarity():
    text = reporting52._fmt_identity({
        "confidence": "media", "turns": 2, "embedded_turns": 2,
        "total_seconds": 10.0, "pair_similarity": 0.43,
        "prototype_similarity_median": 0.85, "rival_similarity_max": 0.75,
        "max_gap_seconds": 82.0,
    })
    assert "entre apariciones 0.43" in text
    assert "rival máx 0.75" in text
    assert "0.85" not in text


def test_selected_raw_candidate_tracks_second_even_after_refined_copy():
    meta = {
        "selection_reason": "seleccion_identity_aware_second",
        "identity_aware_selection": {"enabled": True, "selected_candidate": "second"},
        "candidates": [
            {"threshold": 0.74, "analysis": {"speaker_count": 9}},
            {"threshold": 0.82, "analysis": {"speaker_count": 7}},
        ],
    }
    out = diar52.selected_raw_candidate(meta)
    assert out == {
        "candidate": "second", "index": 1,
        "speaker_count": 7, "threshold": 0.82,
    }


def test_precheck_can_avoid_second_pass_after_acoustic_consolidation():
    engine = diar52.DiarizationEngine(Path("."))
    engine._light_identity = lambda _turns, _ctx: {
        "turns": [{"start": 0, "end": 10, "speaker": i} for i in range(7)],
        "analysis": {"speaker_count": 7, "penalty": 2.4},
        "consistency": {"overall_confidence": "media", "low_confidence_speakers": 0},
        "identity_penalty": 0.8,
        "extraction": {"computed": 12},
        "refinement": {"speakers_before": 9, "speakers_after": 7},
        "wall_seconds": 12.0,
        "new_embedding_calls": 12,
    }
    out = engine._auto_pre_retry({
        "retry_reason": "sobredeteccion_extrema",
        "first_turns": [{}],
        "first_analysis": {"speaker_count": 9},
    })
    assert out["accepted"] is True
    assert out["meta"]["speakers_before"] == 9
    assert out["meta"]["speakers_after"] == 7


def test_validation_keeps_acoustic_and_text_counts_separate():
    meta = {
        "selected_analysis": {"penalty": 2.49},
        "retry": True,
        "stability_delta_speakers": 2,
        "identity_consistency": {"overall_confidence": "media", "insufficient_speakers": 2},
    }
    out = validation52.evaluar(
        meta, acoustic_clusters=7, identity_clusters=7,
        text_speakers=6, unassigned_raw_ids=[5], manual_requested=None,
    )
    assert out["raw_acoustic_clusters"] == 7
    assert out["identity_clusters_after_refinement"] == 7
    assert out["text_assigned_speakers"] == 6
    assert out["unassigned_raw_ids"] == [5]
    assert out["ambiguous"] is True


def test_global_equilibrado_targets_small_and_balanced_diarization():
    p = performance.global_profile("Equilibrado")
    assert p["model"] == "small"
    assert p["asr_profile"] == "Equilibrado"
    assert p["diar_profile"] == "Equilibrada"


def test_migracion_reconoce_preset_solo_si_coincide_completo():
    assert performance.infer_global_profile(
        "small", "Equilibrado", "Equilibrada"
    ) == "Equilibrado"
    assert performance.infer_global_profile(
        "medium", "Preciso", "Precisa"
    ) == "Preciso"
    assert performance.infer_global_profile(
        "medium", "Preciso", "Equilibrada"
    ) == "Personalizado"
    assert performance.infer_global_profile(
        "large-v3", "Preciso", "Precisa"
    ) == "Personalizado"


def test_performance_budget_detects_realtime():
    ok = performance.performance_status({
        "audio_seconds": 404, "processing_seconds": 390,
        "asr_seconds": 250, "diarization_seconds": 140,
    })
    slow = performance.performance_status({
        "audio_seconds": 404, "processing_seconds": 500,
        "asr_seconds": 293, "diarization_seconds": 206,
    })
    assert ok["within_realtime"] is True
    assert slow["within_realtime"] is False
    assert slow["seconds_over_realtime"] == 96
