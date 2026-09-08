import vtt_diarization_process_v4 as dp


class _Cola:
    def __init__(self):
        self.items = []

    def put(self, item):
        self.items.append(item)


def test_worker_transmite_perfil_diarizacion(monkeypatch, tmp_path):
    recibido = {}

    def falso(*args, **kwargs):
        recibido.update(kwargs)
        return ([{"start": 0, "end": 1, "speaker": 0}], {"ok": True})

    monkeypatch.setattr(dp.diar, "diarizar", falso)
    cola = _Cola()
    dp._worker_diarizacion(
        "audio.wav", str(tmp_path), -1, 0.5, None, True, "Rápida", cola
    )
    assert recibido["diar_profile"] == "Rápida"
    assert cola.items[-1][0] == "result"
