import vtt_tuning as tuning


def test_auto_solo_corrige_conteos_extremos():
    assert tuning.ajuste_auto_por_conteo(1) == tuning.AUTO_SPLIT_THRESHOLD
    assert tuning.ajuste_auto_por_conteo(9) == tuning.AUTO_MERGE_THRESHOLD
    assert tuning.ajuste_auto_por_conteo(2) is None
    assert tuning.ajuste_auto_por_conteo(4) is None


def test_regiones_voz_se_activan_solo_si_ahorran():
    segs = [
        {"start": 0, "end": 10, "text": "a"},
        {"start": 30, "end": 40, "text": "b"},
        {"start": 70, "end": 80, "text": "c"},
    ]
    regiones, meta = tuning.regiones_voz_desde_segmentos(segs, 100)
    assert meta["enabled"] is True
    assert len(regiones) == 3
    assert meta["coverage"] < 0.5

    regiones, meta = tuning.regiones_voz_desde_segmentos(
        [{"start": 0, "end": 95, "text": "habla"}], 100
    )
    assert regiones == []
    assert meta["enabled"] is False


def test_hablantes_siempre_consecutivos_por_aparicion():
    out, speakers = tuning.renumerar_hablantes_en_uso([
        {"start": 0, "speaker_id": 5},
        {"start": 1, "speaker_id": 9},
        {"start": 2, "speaker_id": 5},
    ])
    assert [x["speaker"] for x in out] == ["Persona 1", "Persona 2", "Persona 1"]
    assert [x["raw_numeric_id"] for x in speakers] == [5, 9]
