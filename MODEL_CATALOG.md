# Catálogo e integridad de modelos — VtT

**Actualizado:** 9 de septiembre de 2026.

Este documento distingue hashes publicados por una fuente externa de **pins auditados por VtT**. Un pin reproducido evita confiar por primera vez en cualquier contenido distinto del auditado, pero no debe describirse como una firma upstream si upstream no publica el digest.

## 1. Escritorio — diarización sherpa-onnx

Fuente: releases oficiales `k2-fsa/sherpa-onnx`.

La API histórica de GitHub de estos assets muestra `digest=null`. Durante el cierre V5.2 se realizaron dos descargas independientes de los assets oficiales; archive y embedding reprodujeron exactamente los mismos SHA-256. También se auditó el `model.onnx` extraído.

| función | tamaño/archivo | SHA-256 fijado por VtT |
|---|---|---|
| archive segmentación pyannote 3.0 | 6.958.444 bytes | `24615ee884c897d9d2ba09bb4d30da6bb1b15e685065962db5b02e76e4996488` |
| `model.onnx` extraído | contenido del archive anterior | `220ad67ca923bef2fa91f2390c786097bf305bceb5e261d4af67b38e938e1079` |
| embedding 3D-Speaker ERes2Net 16 kHz | 39.593.761 bytes | `1a331345f04805badbb495c775a6ddffcdd1a732567d5ec8b3d5749e3c7a5e4b` |

`vtt_diarization.py` exige ahora tamaño/hash antes de promover la descarga y vuelve a comprobar el ONNX tras extraerlo de forma segura. Un sidecar local antiguo no puede sobreescribir el valor fijado.

V5.2 reutiliza el mismo embedding 3D-Speaker para la verificación de identidad; no descarga un tercer modelo.

## 2. Escritorio — Whisper/CTranslate2

`faster-whisper` gestiona obtención y caché de `tiny`, `base`, `small`, `medium` y `large-v3`. VtT no mantiene actualmente un catálogo de bytes/hashes de todos los repositorios CTranslate2 correspondientes. La política de descarga de esa familia pertenece al stack de dependencia.

Un futuro hardening puede fijar revisiones/hashes por modelo, pero no debe inventar digests ni asumir que un nombre móvil representa bytes inmutables.

## 3. Android — GGML whisper.cpp

Fuente configurada: `https://huggingface.co/ggerganov/whisper.cpp/resolve/main/`.

Catálogo esperado por `ModelManager`:

| id | archivo | SHA-256 esperado |
|---|---|---|
| tiny | `ggml-tiny.bin` | `be07e048e1e599ad46341c8d2a135645097a538221678b7acdd1b1919c6e1b21` |
| base | `ggml-base.bin` | `60ed5bc3dd14eea856493d334349b405782ddcaf0028d4b5df4088345fba2efe` |
| small | `ggml-small.bin` | `1be3a9b2063867b937e64e2ec7483364a79917e157fa98c5d94b5c1fffea987b` |

Flujo:

1. descarga/reanudación a `.part`;
2. validación de rango/tamaño cuando el servidor lo informa;
3. SHA-256 del archivo completo;
4. comparación contra catálogo;
5. promoción al nombre final solo si coincide;
6. sidecars `.size`/`.sha256` para integridad/caché posteriores.

Un modelo previo que no coincide se descarta y debe reacquirirse.

## 4. whisper.cpp nativo Android

La fuente C++ está fijada al commit exacto:

```text
8a9ad7844d6e2a10cddf4b92de4089d7ac2b14a9
```

correspondiente al tag `v1.7.4` auditado durante el cierre previo. Cambiar ese commit exige nueva compilación Android y revisión de API/JNI.

## 5. Política de actualización

Un cambio de modelo o pin debe registrar:

- fuente exacta;
- fecha;
- tamaño cuando sea útil;
- digest esperado y cómo se obtuvo;
- si el digest es upstream o un pin auditado por VtT;
- smoke/CI posterior.

No actualizar automáticamente estos valores a partir de una descarga no revisada.
