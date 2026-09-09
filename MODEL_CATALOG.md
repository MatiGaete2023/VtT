# Catálogo e integridad de modelos — VtT

**Actualizado:** 9 de septiembre de 2026.

Este documento distingue dos familias de modelos con mecanismos de integridad diferentes. No se incorporan SHA-256 supuestos ni calculados desde una fuente no confiable como si fueran digests oficiales.

## 1. Escritorio — modelos de diarización

VtT usa actualmente:

| función | artefacto | fuente | comprobación inicial | comprobación posterior |
|---|---|---|---|---|
| segmentación | pyannote segmentation 3.0 para sherpa-onnx | release oficial k2-fsa/GitHub | HTTPS + tamaño exacto esperado | SHA-256 local fijado tras la primera descarga |
| embedding | 3D-Speaker ERes2Net 16 kHz | release oficial k2-fsa/GitHub | HTTPS + tamaño exacto esperado | SHA-256 local fijado tras la primera descarga |

Los assets históricos consultados para estos modelos no publican en su metadata un digest SHA-256 de origen utilizable por VtT. Por eso el primer download **no se presenta como autenticado criptográficamente**. El pin local sirve para detectar cambios/corrupción posteriores.

V5.1 reutiliza el mismo modelo 3D-Speaker para la comprobación de consistencia de identidad; no descarga un tercer modelo.

## 2. Escritorio — modelos Whisper

`faster-whisper` gestiona la obtención/caché de los modelos Whisper/CTranslate2 seleccionados (`tiny`, `base`, `small`, `medium`, `large-v3`). La política de integridad de esa descarga pertenece al stack de la dependencia. VtT no mantiene actualmente un catálogo propio de hashes para esos repositorios.

## 3. Android — modelos GGML de whisper.cpp

Modelos ofrecidos por la app:

| id | archivo |
|---|---|
| tiny | `ggml-tiny.bin` |
| base | `ggml-base.bin` |
| small | `ggml-small.bin` |

Fuente actual: `https://huggingface.co/ggerganov/whisper.cpp/resolve/main/`.

`ModelManager` implementa:

- descarga a `.part`;
- reanudación mediante `Range` cuando el servidor la admite;
- validación de `Content-Range` antes de anexar;
- comprobación del tamaño total recibido cuando el servidor lo informa;
- cálculo SHA-256 al terminar;
- sidecars `.size` y `.sha256`;
- verificación del hash en ejecuciones posteriores (con caché por tamaño/mtime).

Esto protege contra truncamiento y corrupción local posterior, pero el hash se aprende **después de la primera descarga**. No autentica la primera recepción frente a una fuente comprometida.

## 4. Pendiente de hardening

[CONFLICTO_ABIERTO] Para autenticar la primera descarga de cada GGML Android hace falta un catálogo mantenible de:

- revisión/publicación inmutable;
- bytes exactos;
- SHA-256 esperado;
- fuente independiente o publicación oficial del digest.

No completar esa tabla hasta obtener valores verificables. La política es preferir una limitación explícita antes que un hash inventado.

Cuando se implemente un catálogo de origen, la descarga deberá:

1. resolver una URL/revisión inmutable;
2. descargar a `.part`;
3. validar tamaño;
4. calcular SHA-256;
5. comparar contra el digest esperado del catálogo;
6. promover a archivo final solo si coincide;
7. conservar el último modelo válido si una actualización falla.
