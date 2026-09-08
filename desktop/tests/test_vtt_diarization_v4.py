import vtt_diarization_v4 as d4


def test_perfiles_diarizacion_tienen_resolucion_distinta():
    assert d4.DIARIZATION_PROFILES["Rápida"]["window_shift_ratio"] == 0.25
    assert d4.DIARIZATION_PROFILES["Equilibrada"]["window_shift_ratio"] == 0.20
    assert d4.DIARIZATION_PROFILES["Precisa"]["window_shift_ratio"] == 0.10


def test_auto_detecta_tramo_monopolizado_y_pide_separar():
    turnos = [
        {"start": 0.0, "end": 80.0, "speaker": 0},
        {"start": 80.0, "end": 100.0, "speaker": 1},
        {"start": 100.0, "end": 120.0, "speaker": 2},
    ]
    analisis = d4.analizar_turnos(turnos, 120.0)
    threshold, motivo = d4.decidir_reintento(analisis)
    assert analisis["speaker_count"] == 3
    assert analisis["longest_turn_seconds"] == 80.0
    assert threshold == d4.AUTO_SPLIT_THRESHOLD
    assert motivo == "tramo_monopolizado"


def test_auto_estable_no_repite():
    turnos = [
        {"start": 0.0, "end": 20.0, "speaker": 0},
        {"start": 20.0, "end": 40.0, "speaker": 1},
        {"start": 40.0, "end": 60.0, "speaker": 2},
        {"start": 60.0, "end": 80.0, "speaker": 0},
        {"start": 80.0, "end": 100.0, "speaker": 1},
        {"start": 100.0, "end": 120.0, "speaker": 2},
    ]
    analisis = d4.analizar_turnos(turnos, 120.0)
    threshold, motivo = d4.decidir_reintento(analisis)
    assert threshold is None
    assert motivo is None


def test_seleccion_prefiere_segunda_pasada_si_mejora_estructura():
    a = {"speaker_count": 3, "penalty": 1.5}
    b = {"speaker_count": 5, "penalty": 0.2}
    t1 = [{"start": 0, "end": 1, "speaker": 0}]
    t2 = [{"start": 0, "end": 1, "speaker": 1}]
    turnos, analisis, razon = d4.elegir_candidato(
        (t1, a), (t2, b), "tramo_monopolizado"
    )
    assert turnos == t2
    assert analisis is b
    assert razon == "segunda_pasada_mejora_estructura"


def test_seleccion_no_acepta_salto_inestable_sin_mejora():
    a = {"speaker_count": 3, "penalty": 0.5}
    b = {"speaker_count": 8, "penalty": 0.1}
    t1 = [{"start": 0, "end": 1, "speaker": 0}]
    t2 = [{"start": 0, "end": 1, "speaker": 1}]
    turnos, _analisis, razon = d4.elegir_candidato(
        (t1, a), (t2, b), "tramo_monopolizado"
    )
    assert turnos == t1
    assert razon == "se_conserva_primera_pasada"
