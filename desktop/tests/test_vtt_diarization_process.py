import queue

import pytest

import vtt_diarization_process as dp


def test_estimar_restante():
    assert dp.estimar_restante(50, 10) == pytest.approx(10)
    assert dp.estimar_restante(25, 10) == pytest.approx(30)
    assert dp.estimar_restante(0, 10) is None
    assert dp.estimar_restante(100, 10) == 0


class _ProcesoFalso:
    def __init__(self, args, cancelar=False):
        self.args = args
        self._alive = True
        self.exitcode = None
        self.terminated = False
        self.cancelar = cancelar

    def start(self):
        cola = self.args[-1]
        if not self.cancelar:
            cola.put(("progress", 50.0))
            cola.put(("result", [{"start": 0.0, "end": 1.0, "speaker": 0}]))
            self._alive = False
            self.exitcode = 0

    def is_alive(self):
        return self._alive

    def terminate(self):
        self.terminated = True
        self._alive = False
        self.exitcode = -15

    def join(self, timeout=None):
        return None


class _ColaFalsa(queue.Queue):
    def close(self):
        pass

    def join_thread(self):
        pass


class _ContextoFalso:
    def __init__(self, cancelar=False):
        self.cancelar = cancelar
        self.proceso = None

    def Queue(self):
        return _ColaFalsa()

    def Process(self, target, args, daemon):
        self.proceso = _ProcesoFalso(args, cancelar=self.cancelar)
        return self.proceso


def test_diarizar_responsivo_transmite_progreso(monkeypatch, tmp_path):
    ctx = _ContextoFalso()
    monkeypatch.setattr(dp.mp, "get_context", lambda _modo: ctx)
    avances = []
    out = dp.diarizar_responsivo(
        "audio.wav", tmp_path, progreso=avances.append
    )
    assert out[0]["speaker"] == 0
    assert 50.0 in avances
    assert avances[-1] == 100.0


def test_diarizar_responsivo_cancela_proceso(monkeypatch, tmp_path):
    ctx = _ContextoFalso(cancelar=True)
    monkeypatch.setattr(dp.mp, "get_context", lambda _modo: ctx)
    with pytest.raises(dp.DiarizacionCancelada):
        dp.diarizar_responsivo(
            "audio.wav", tmp_path, cancelado=lambda: True
        )
    assert ctx.proceso is not None
    assert ctx.proceso.terminated is True
