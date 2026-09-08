# Catálogo confiable de modelos

Estado: **[CONFLICTO_ABIERTO]**. La aplicación actual comprueba el hash que
calcula después de recibir un modelo; eso detecta corrupción local posterior,
pero no autentica la primera descarga.

No se incorporan hashes supuestos. Antes de activar esta fase hay que obtener,
desde la publicación de cada modelo, una revisión inmutable, tamaño y SHA-256
verificable para tiny, base, small y los archivos auxiliares que se agreguen.

| id | publicación/revisión inmutable | archivo | bytes | SHA-256 | fuente de la suma |
|---|---|---|---:|---|---|
| tiny | pendiente | ggml-tiny.bin | pendiente | pendiente | pendiente |
| base | pendiente | ggml-base.bin | pendiente | pendiente | pendiente |
| small | pendiente | ggml-small.bin | pendiente | pendiente | pendiente |

La implementación deberá rechazar una descarga nueva que no coincida con una
entrada completa del catálogo, descargar a .part, validar Content-Range y
promover el archivo solo tras verificarlo. Debe conservar el último modelo
válido si falla la actualización.
