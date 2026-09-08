from vtt_tuning import AUTO_CLUSTER_THRESHOLD, renumerar_hablantes_en_uso


def test_auto_threshold_es_conservador():
    assert AUTO_CLUSTER_THRESHOLD == 0.90


def test_renumera_solo_hablantes_usados_por_primera_aparicion():
    segmentos = [
        {"start": 0.0, "end": 2.0, "text": "a", "speaker_id": 3, "speaker": "Persona 4"},
        {"start": 2.0, "end": 4.0, "text": "b", "speaker_id": 9, "speaker": "Persona 10"},
        {"start": 4.0, "end": 6.0, "text": "c", "speaker_id": 3, "speaker": "Persona 4"},
        {"start": 6.0, "end": 8.0, "text": "d", "speaker_id": 14, "speaker": "Persona 15"},
    ]

    salida, speakers = renumerar_hablantes_en_uso(segmentos)

    assert [x["speaker"] for x in salida] == [
        "Persona 1", "Persona 2", "Persona 1", "Persona 3"
    ]
    assert [x["speaker_id"] for x in salida] == [0, 1, 0, 2]
    assert [x["speaker_raw_id"] for x in salida] == [3, 9, 3, 14]
    assert [x["display_name"] for x in speakers] == [
        "Persona 1", "Persona 2", "Persona 3"
    ]
    assert [x["raw_numeric_id"] for x in speakers] == [3, 9, 14]


def test_segmento_sin_hablante_se_conserva():
    salida, speakers = renumerar_hablantes_en_uso([
        {"start": 0.0, "end": 1.0, "text": "silencio", "speaker_id": None, "speaker": None}
    ])
    assert salida[0]["speaker"] is None
    assert speakers == []
