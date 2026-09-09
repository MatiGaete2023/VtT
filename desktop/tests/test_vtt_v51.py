import numpy as np

import vtt_identity as identity
import vtt_validation_v51 as validation51

A = np.array([1.0, 0.0, 0.0], dtype=np.float32)
B = np.array([0.0, 1.0, 0.0], dtype=np.float32)
C = np.array([0.0, 0.0, 1.0], dtype=np.float32)


def test_outlier_reassigns_to_existing_identity():
    turns = [
        {"start": 0, "end": 5, "speaker": 0},
        {"start": 10, "end": 15, "speaker": 0},
        {"start": 20, "end": 25, "speaker": 0},
        {"start": 30, "end": 35, "speaker": 1},
        {"start": 40, "end": 45, "speaker": 1},
    ]
    out, meta = identity.refinar_turnos(turns, {0: A, 1: A, 2: B, 3: B, 4: B})
    assert out[2]["speaker"] == 1
    assert meta["reassigned_turns"] == 1


def test_microcluster_only_merges_with_strong_acoustic_match():
    turns = [
        {"start": 0, "end": 6, "speaker": 0},
        {"start": 10, "end": 16, "speaker": 0},
        {"start": 20, "end": 21, "speaker": 2},
    ]
    out, _ = identity.refinar_turnos(turns, {0: A, 1: A, 2: A})
    assert out[2]["speaker"] == 0
    out2, _ = identity.refinar_turnos(turns, {0: A, 1: A, 2: C})
    assert out2[2]["speaker"] == 2


def test_long_turn_not_used_as_prototype():
    turns = [{"start": 0, "end": 30, "speaker": 0}, {"start": 40, "end": 45, "speaker": 0}]
    calls = []
    def cb(a, b):
        calls.append((a, b)); return A
    emb, meta = identity.extraer_embeddings_turnos(turns, cb)
    assert 0 not in emb and 1 in emb
    assert meta["skipped_long"] == 1
    assert calls == [(40.0, 45.0)]


def test_local_scan_reassigns_sustained_match_to_known_identity():
    turns = [
        {"start": 0.0, "end": 25.0, "speaker": 0},
        {"start": 30.0, "end": 34.0, "speaker": 1},
        {"start": 36.0, "end": 40.0, "speaker": 1},
    ]
    def cb(a, b):
        mid = (a + b) / 2
        return B if 9 <= mid <= 17 or 29 <= mid <= 41 else A
    out, meta = identity.escanear_cambios_locales(turns, cb, allow_new_identities=True, enabled=True)
    assert {t["speaker"] for t in out} <= {0, 1}
    assert any(t["speaker"] == 1 and t["start"] < 15 < t["end"] for t in out)
    assert meta["applied_changes"] == 1


def test_local_scan_without_current_prototype_does_not_invent_identity():
    turns = [
        {"start": 0.0, "end": 25.0, "speaker": 0},
        {"start": 30.0, "end": 34.0, "speaker": 1},
        {"start": 36.0, "end": 40.0, "speaker": 1},
    ]
    def cb(a, b):
        return B if (a + b) / 2 >= 29 else A
    out, _ = identity.escanear_cambios_locales(turns, cb, allow_new_identities=True, enabled=True)
    assert {t["speaker"] for t in out} <= {0, 1}
    assert all(t["speaker"] == 0 for t in out if t["end"] <= 25.01)


def test_consistency_gaps_are_chronological():
    turns = [
        {"start": 20, "end": 22, "speaker": 0},
        {"start": 0, "end": 3, "speaker": 0},
        {"start": 10, "end": 12, "speaker": 0},
    ]
    s = identity.resumir_identidades(turns, {0: A, 1: A, 2: A})["speakers"][0]
    assert s["max_gap_seconds"] == 8.0


def test_identity_low_confidence_downgrades_validation():
    base = {"status": "estimacion_acustica_estable", "estimated_speakers": 4}
    out = validation51.aplicar_consistencia_identidad(
        base, {"overall_confidence": "baja", "low_confidence_speakers": 1}
    )
    assert out["status"] == "estimacion_sospechosa_identidad"


def test_manual_count_is_not_relabelled_as_estimation():
    base = {"status": "conteo_fijado_por_usuario", "estimated_speakers": 4}
    out = validation51.aplicar_consistencia_identidad(base, {"overall_confidence": "baja"})
    assert out["status"] == "conteo_fijado_por_usuario"
    assert validation51.etiqueta_confianza(out) == "conteo fijado por usuario"
