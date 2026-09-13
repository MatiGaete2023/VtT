# VtT Ultra Windows

Rama: `windows-ultra-fast`

Esta variante existe para un objetivo distinto de V5.2.1 estable: **procesar lo antes posible en Windows CPU**, manteniendo transcripción local, timestamps útiles e intento de separación de hablantes.

## 1. Modos disponibles

### Ultra Máxima

Ruta de borrador inmediato:

- Whisper `tiny`;
- ASR `Rápido`;
- batch 8 / beam 1;
- hablantes `Auto`;
- diarización `Ultrarrápida`;
- `window_shift_ratio = 0.35`;
- threshold Auto único `0.82`;
- **1 pasada Sherpa**;
- sin identidad V5.2;
- alineación por segmento ASR;
- timestamps por palabra no forzados.

### Ultra Calidad 90s

Ruta que usa deliberadamente parte del margen de velocidad para recuperar calidad:

- Whisper `base`;
- ASR `Rápido`;
- batch 8 / beam 1;
- hablantes `Auto`;
- misma diarización `Ultrarrápida 0.35`;
- mismo threshold Auto `0.82`;
- **1 pasada Sherpa**;
- timestamps por palabra activados internamente;
- alineación palabra ↔ turno Sherpa y división de segmentos cuando cambia la voz;
- identidad acústica ligera: máximo 10 embeddings y máximo 2 por cluster;
- puede reconciliar clusters existentes, pero no crea identidades nuevas;
- sin segunda pasada Sherpa;
- sin escaneo largo V5.2;
- re-ASR selectivo con modelo superior **desactivado hasta medir el presupuesto real**.

La elección entre los dos modos Ultra se conserva entre sesiones. Una configuración histórica ajena a esta rama se migra a Ultra Máxima.

## 2. Motivo del modo Calidad

La primera prueba real de Ultra Máxima se hizo con el mismo video de referencia de 6:44 (404,004 s) en el PC institucional Windows.

Resultados:

- carga modelo: 8,86 s;
- ASR: 10,32 s;
- diarización completa: 41,51 s;
- Sherpa `process()` wall: 33,77 s;
- procesamiento: 51,84 s;
- extremo a extremo: 60,77 s;
- velocidad: 7,79× tiempo real;
- Sherpa encontró 6 clusters acústicos y 40 turnos;
- Whisper produjo 15 segmentos;
- solo 3 clusters terminaron asociados a texto.

El diagnóstico fue que la velocidad ya era sobrada; la pérdida principal estaba en la **alineación por segmento**: cada segmento Whisper largo recibía un único hablante aunque Sherpa hubiera detectado cambios de voz dentro de él.

Por eso Ultra Calidad 90s no añade otra pasada acústica. Aprovecha mejor la información que la primera pasada ya calculó.

## 3. Presupuesto de diseño

Para Ultra Calidad se usa una referencia de:

`processing_seconds <= 0.22 × duración del audio`

En el video patrón:

`404 s × 0.22 ≈ 88,9 s`

Es un **objetivo de diseño**, no una garantía. Solo una nueva prueba en el PC institucional puede demostrar el tiempo efectivo.

Ultra Máxima conserva su referencia más amplia de `0.60 × duración`, aunque la prueba real quedó muy por debajo.

## 4. Identidad ligera

La identidad ligera reutiliza el PCM que Sherpa ya decodificó y el mismo modelo de embeddings. Tiene un tope duro de trabajo:

- máximo 10 embeddings por archivo;
- máximo 2 embeddings por cluster;
- sin escaneo detallado de turnos largos;
- `allow_new_identities=False`;
- sin precheck para decidir otra pasada, porque Ultra nunca repite Sherpa.

Su finalidad no es convertir Auto en ground truth. Solo intenta reconciliar inconsistencias evidentes con un costo acotado.

## 5. Alineación de hablantes

Ultra Máxima mantiene `segment_overlap`.

Ultra Calidad usa `vtt_alignment.alinear_y_dividir()`:

1. Whisper entrega timestamps por palabra;
2. cada palabra se cruza temporalmente con los turnos Sherpa;
3. se suavizan flips interiores extremadamente breves;
4. el segmento se divide cuando la secuencia de palabras cambia de hablante;
5. los timestamps por palabra pueden ser internos: si el usuario no los pidió como salida, se eliminan antes de exportar.

Esto busca recuperar en texto clusters que Ultra Máxima detectaba acústicamente pero perdía al asignar cada segmento completo a una sola Persona.

## 6. Qué no se implementó todavía

No se activó re-ASR selectivo con `base`/`small` sobre fragmentos dudosos. El modo Calidad ya cambia el ASR principal de `tiny` a `base`; antes de añadir una segunda transcripción parcial necesitamos saber cuánto tarda realmente esta combinación en el PC institucional.

Si la prueba queda holgadamente bajo 90 s, el siguiente candidato será dedicar parte del margen a re-ASR selectivo de los segmentos con peor confianza.

## 7. Windows

Objetivo principal: Windows 10/11, CPU `int8`, sin privilegios de administrador.

En `desktop/`:

```bat
run.bat
```

o:

```bat
python run.py
```

El selector `Modo global` ofrece `Ultrarrápido` y `Ultra Calidad 90s`.

## 8. Verificación automatizada — 13/09/2026

### Windows Ultra checks #104

Run `34732920777`, commit funcional `1016029928b9127348c615f0f66468498d9aa82b`: **success**.

Se ejecutaron `py_compile` y **105 pruebas**, todas correctas. La suite incluye regresiones para:

- ambos presets Ultra;
- Ultra Máxima sin timestamps por palabra forzados;
- Ultra Calidad con timestamps por palabra internos;
- una sola pasada y `adaptive=False`;
- identidad ligera solo en Calidad;
- división palabra ↔ hablante;
- conservación separada de clusters Sherpa, clusters tras identidad y hablantes con texto;
- salida Auto marcada como estimación limitada;
- persistencia de la elección del modo Ultra.

### PyInstaller Windows — executable #14

Run `34733015747`, commit de build `e41ce37267ff8a8651fc8459f2f5aba088b07de2`: **success**.

Artefacto GitHub Actions:

```text
VtT-Ultra-Windows
127.425.214 bytes
sha256:6ad24ec13669363b5574fec1831021eeede01a69e74569ea6f8098e1abf929d7
expira: 12 de diciembre de 2026
```

El digest corresponde al artefacto/ZIP publicado por GitHub Actions; no es una firma Authenticode del `.exe` interior.

Después del empaquetado, `.github/workflows/desktop-build.yml` fue restaurado a ejecución manual (`workflow_dispatch`) con su contenido permanente.

## 9. Próxima prueba real

Usar exactamente el mismo video de 6:44 y el mismo PC institucional, seleccionando:

`Modo global: Ultra Calidad 90s`

Guardar al menos JSON y Word.

Comparar con Ultra Máxima:

- carga de modelo;
- ASR;
- diarización;
- identidad ligera;
- procesamiento y extremo a extremo;
- segmentos ASR de entrada vs segmentos finales;
- cambios internos detectados;
- clusters Sherpa;
- clusters tras identidad ligera;
- Personas con texto;
- clusters acústicos sin texto;
- calidad léxica visible.

Criterio experimental principal: comprobar si mejora materialmente texto y separación de voces manteniendo el procesamiento aproximadamente en **90 s o menos**.
