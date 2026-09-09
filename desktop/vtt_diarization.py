#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Diarización local opcional para VtT usando sherpa-onnx.

Los modelos se descargan solo cuando el usuario activa diarización. Los assets
históricos de sherpa-onnx no publican ``digest`` en la API de GitHub; para
eliminar el TOFU anterior, VtT fija los SHA-256 observados y repetidos en dos
descargas independientes desde los assets oficiales el 9 de septiembre de
2026. Tanto el archivo comprimido como el ONNX extraído y el embedding deben
coincidir exactamente antes de ser usados.
"""
from __future__ import annotations

import hashlib
import os
import tarfile
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


SEGMENTATION_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/"
    "speaker-segmentation-models/sherpa-onnx-pyannote-segmentation-3-0.tar.bz2"
)
SEGMENTATION_ARCHIVE_SIZE = 6_958_444
SEGMENTATION_ARCHIVE_SHA256 = (
    "24615ee884c897d9d2ba09bb4d30da6bb1b15e685065962db5b02e76e4996488"
)
SEGMENTATION_MODEL_SHA256 = (
    "220ad67ca923bef2fa91f2390c786097bf305bceb5e261d4af67b38e938e1079"
)
EMBEDDING_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/"
    "speaker-recongition-models/3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx"
)
EMBEDDING_SIZE = 39_593_761
EMBEDDING_SHA256 = (
    "1a331345f04805badbb495c775a6ddffcdd1a732567d5ec8b3d5749e3c7a5e4b"
)


def sha256_archivo(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(1024 * 1024), b""):
            h.update(bloque)
    return h.hexdigest()


def _leer_hash_pin(ruta: Path) -> Optional[str]:
    pin = ruta.with_suffix(ruta.suffix + ".sha256")
    try:
        valor = pin.read_text(encoding="utf-8").strip().lower()
        return valor if len(valor) == 64 else None
    except OSError:
        return None


def _guardar_hash_pin(ruta: Path, valor: Optional[str] = None) -> str:
    esperado = (valor or sha256_archivo(ruta)).lower()
    ruta.with_suffix(ruta.suffix + ".sha256").write_text(
        esperado + "\n", encoding="utf-8"
    )
    return esperado


def validar_archivo_modelo(
    ruta: Path,
    tamano: Optional[int] = None,
    sha256_esperado: Optional[str] = None,
) -> Tuple[bool, str]:
    if not ruta.is_file():
        return False, "no existe"
    if tamano is not None and ruta.stat().st_size != tamano:
        return False, f"tamaño inesperado: {ruta.stat().st_size} != {tamano}"

    esperado = sha256_esperado.lower() if sha256_esperado else None
    pin = _leer_hash_pin(ruta)
    # Si existe un hash de origen fijado, es la autoridad. El sidecar local es
    # solo caché/proveniencia y no puede sustituirlo.
    if esperado is not None:
        actual = sha256_archivo(ruta)
        if actual != esperado:
            return False, "SHA-256 no coincide con el valor auditado"
        if pin != esperado:
            try:
                _guardar_hash_pin(ruta, esperado)
            except OSError:
                pass
        return True, "ok"

    if pin:
        actual = sha256_archivo(ruta)
        if actual != pin:
            return False, "SHA-256 local no coincide"
    return True, "ok"


def _descargar(
    url: str,
    destino: Path,
    tamano: int,
    sha256_esperado: str,
    log: Callable[[str], None],
) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    parcial = destino.with_suffix(destino.suffix + ".part")
    parcial.unlink(missing_ok=True)
    log(f"Descargando modelo de diarización: {destino.name}")
    req = urllib.request.Request(url, headers={"User-Agent": "VtT/2"})
    with urllib.request.urlopen(req, timeout=60) as resp, parcial.open("wb") as out:
        while True:
            bloque = resp.read(1024 * 1024)
            if not bloque:
                break
            out.write(bloque)
    if parcial.stat().st_size != tamano:
        obtenido = parcial.stat().st_size
        parcial.unlink(missing_ok=True)
        raise RuntimeError(
            f"Descarga incompleta de {destino.name}: {obtenido} bytes; "
            f"esperados {tamano}"
        )
    actual = sha256_archivo(parcial)
    if actual != sha256_esperado.lower():
        parcial.unlink(missing_ok=True)
        raise RuntimeError(
            f"SHA-256 inesperado para {destino.name}; la descarga no coincide "
            "con el asset auditado de VtT"
        )
    os.replace(parcial, destino)
    _guardar_hash_pin(destino, sha256_esperado)


def _extraer_modelo_segmentacion(archivo: Path, destino: Path) -> None:
    """Extrae solo model.onnx por flujo; nunca usa extractall (evita path traversal)."""
    with tarfile.open(archivo, mode="r:bz2") as tar:
        candidatos = [
            m for m in tar.getmembers()
            if m.isfile() and m.name.endswith("/model.onnx")
        ]
        if not candidatos:
            candidatos = [
                m for m in tar.getmembers()
                if m.isfile() and m.name == "model.onnx"
            ]
        if len(candidatos) != 1:
            raise RuntimeError(
                "El paquete de segmentación no contiene un model.onnx único"
            )
        src = tar.extractfile(candidatos[0])
        if src is None:
            raise RuntimeError("No se pudo leer model.onnx del paquete")
        parcial = destino.with_suffix(".onnx.part")
        with parcial.open("wb") as out:
            while True:
                bloque = src.read(1024 * 1024)
                if not bloque:
                    break
                out.write(bloque)
        actual = sha256_archivo(parcial)
        if actual != SEGMENTATION_MODEL_SHA256:
            parcial.unlink(missing_ok=True)
            raise RuntimeError(
                "El model.onnx extraído no coincide con el hash auditado"
            )
        os.replace(parcial, destino)
        _guardar_hash_pin(destino, SEGMENTATION_MODEL_SHA256)


def asegurar_modelos(
    carpeta: Path,
    log: Optional[Callable[[str], None]] = None,
) -> Tuple[Path, Path]:
    log = log or (lambda _: None)
    carpeta.mkdir(parents=True, exist_ok=True)
    seg_model = carpeta / "pyannote-segmentation-3.0.onnx"
    emb_model = carpeta / "3dspeaker-eres2net-base-16k.onnx"

    ok_seg, _ = validar_archivo_modelo(
        seg_model, sha256_esperado=SEGMENTATION_MODEL_SHA256
    )
    if not ok_seg:
        # Descarta un ONNX antiguo/corrupto: desde V5.2 no se confía en su
        # sidecar histórico; se reconstruye desde un archive autenticado.
        seg_model.unlink(missing_ok=True)
        seg_model.with_suffix(seg_model.suffix + ".sha256").unlink(missing_ok=True)
        archivo = carpeta / "sherpa-onnx-pyannote-segmentation-3-0.tar.bz2"
        ok_archivo, _ = validar_archivo_modelo(
            archivo,
            SEGMENTATION_ARCHIVE_SIZE,
            SEGMENTATION_ARCHIVE_SHA256,
        )
        if not ok_archivo:
            archivo.unlink(missing_ok=True)
            archivo.with_suffix(archivo.suffix + ".sha256").unlink(missing_ok=True)
            _descargar(
                SEGMENTATION_URL,
                archivo,
                SEGMENTATION_ARCHIVE_SIZE,
                SEGMENTATION_ARCHIVE_SHA256,
                log,
            )
        _extraer_modelo_segmentacion(archivo, seg_model)
        archivo.unlink(missing_ok=True)
        archivo.with_suffix(archivo.suffix + ".sha256").unlink(missing_ok=True)

    ok_emb, _ = validar_archivo_modelo(
        emb_model, EMBEDDING_SIZE, EMBEDDING_SHA256
    )
    if not ok_emb:
        emb_model.unlink(missing_ok=True)
        emb_model.with_suffix(emb_model.suffix + ".sha256").unlink(missing_ok=True)
        _descargar(
            EMBEDDING_URL,
            emb_model,
            EMBEDDING_SIZE,
            EMBEDDING_SHA256,
            log,
        )

    return seg_model, emb_model


def decodificar_audio_mono(ruta: str, sample_rate: int) -> Any:
    """Decodifica cualquier formato aceptado por PyAV a float32 mono."""
    import av
    import numpy as np

    piezas = []
    cont = av.open(ruta)
    try:
        stream = next((s for s in cont.streams if s.type == "audio"), None)
        if stream is None:
            raise ValueError("El archivo no contiene pista de audio")
        resampler = av.AudioResampler(
            format="fltp", layout="mono", rate=sample_rate
        )
        for frame in cont.decode(stream):
            for rf in resampler.resample(frame):
                arr = rf.to_ndarray()
                mono = arr[0] if arr.ndim > 1 else arr
                piezas.append(np.asarray(mono, dtype=np.float32))
        try:
            finales = resampler.resample(None) or []
        except Exception:
            finales = []
        for rf in finales:
            arr = rf.to_ndarray()
            piezas.append(
                np.asarray(arr[0] if arr.ndim > 1 else arr, dtype=np.float32)
            )
    finally:
        cont.close()
    if not piezas:
        raise ValueError("No se pudo decodificar audio")
    return np.ascontiguousarray(np.concatenate(piezas))


def diarizar(
    ruta: str,
    carpeta_modelos: Path,
    num_speakers: int = -1,
    threshold: float = 0.5,
    log: Optional[Callable[[str], None]] = None,
    progreso: Optional[Callable[[float], None]] = None,
) -> List[Dict[str, Any]]:
    """Devuelve turnos {start,end,speaker}. Todo el procesamiento es local."""
    log = log or (lambda _: None)
    progreso = progreso or (lambda _: None)
    import sherpa_onnx

    seg_model, emb_model = asegurar_modelos(carpeta_modelos, log)
    config = sherpa_onnx.OfflineSpeakerDiarizationConfig(
        segmentation=sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
            pyannote=sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(
                model=str(seg_model), window_shift_ratio=0.1
            )
        ),
        embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(
            model=str(emb_model)
        ),
        clustering=sherpa_onnx.FastClusteringConfig(
            num_clusters=int(num_speakers), threshold=float(threshold)
        ),
        min_duration_on=0.3,
        min_duration_off=0.5,
    )
    if not config.validate():
        raise RuntimeError(
            "Configuración de diarización inválida; revisa los modelos"
        )
    sd = sherpa_onnx.OfflineSpeakerDiarization(config)
    log("Decodificando audio para identificar hablantes…")
    audio = decodificar_audio_mono(ruta, int(sd.sample_rate))

    def callback(procesados: int, total: int) -> int:
        if total:
            progreso(
                min(100.0, max(0.0, procesados / total * 100.0))
            )
        return 0

    log("Identificando cambios de hablante…")
    resultado = sd.process(audio, callback=callback).sort_by_start_time()
    turnos = [
        {"start": float(r.start), "end": float(r.end), "speaker": int(r.speaker)}
        for r in resultado
        if float(r.end) > float(r.start)
    ]
    progreso(100.0)
    return turnos
