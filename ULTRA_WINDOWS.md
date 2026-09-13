# VtT Ultra Windows

Rama: `windows-ultra-fast`

Esta variante existe para un objetivo distinto de V5.2.1 estable: **terminar lo antes posible en Windows CPU**, manteniendo transcripción local, timestamps útiles e intento de separación de hablantes.

## Configuración por defecto

- modelo Whisper: `tiny`;
- ASR: `Rápido`;
- batching: 8;
- beam: 1;
- hablantes: `Auto`;
- diarización: `Ultrarrápida`;
- `window_shift_ratio`: `0.35`;
- threshold Auto único: `0.82`;
- pasadas Sherpa: **1**;
- verificación V5.2 de identidad: **omitida**;
- alineación voz/texto: máximo solapamiento por **segmento ASR**;
- timestamps por palabra: no se fuerzan. Si el usuario los activa manualmente, se respetan.

## Qué conserva

- ejecución local/offline;
- checkpoint ASR recuperable antes de diarización;
- timestamps de inicio/fin de cada segmento;
- etiquetas `Persona N` cuando Sherpa logra separar clusters;
- reducción de diarización a regiones donde ASR detectó voz cuando es seguro;
- worker persistente y reutilización de modelos Sherpa;
- cancelación normal;
- TXT, Markdown, SRT, VTT, JSON y Word;
- métricas de ASR, Sherpa, exportación y tiempo extremo a extremo.

## Qué sacrifica para ser más rápida

1. No realiza una segunda pasada Sherpa aunque Auto parezca dudoso.
2. No ejecuta la verificación/refinamiento de identidad V5.2.
3. No fuerza timestamps por palabra solo para diarización.
4. Un cambio de voz dentro de un segmento Whisper puede quedar bajo una sola `Persona N`.
5. `shift 0.35` tiene menor resolución temporal que Rápida 0.25 / Equilibrada 0.20.
6. Auto es una estimación rápida; JSON/Word lo marca como `estimacion_ultra_una_pasada`.

La variante no debe utilizarse cuando la separación fina de hablantes sea más importante que la velocidad. Para esos casos usar la rama V5.2.1 estable.

## Windows

Objetivo principal: Windows 10/11, CPU `int8`, sin privilegios de administrador.

En `desktop/`:

```bat
run.bat
```

o:

```bat
python run.py
```

El título de la aplicación indica `VtT Ultra Windows` para evitar confundirla con la versión estable.

## Criterio de rendimiento

El preset Ultra usa un objetivo orientativo de `processing_seconds <= 0.60 * audio_seconds`. No es una garantía. El hardware institucional debe medirse con el mismo archivo utilizado en campañas anteriores.

Para un audio de 6:44 (404 s), el objetivo nominal es aproximadamente 242 s de procesamiento. La rama no repite Sherpa para intentar alcanzar ese objetivo.

## Verificación automatizada — 13/09/2026

### Windows Ultra checks

La ruta final de código quedó verificada en Windows con `py_compile` y la suite completa de pruebas. La campaña final incorporó las regresiones Ultra y comprobó, entre otros puntos:

- preset `tiny + Rápido + Auto + Ultrarrápida`;
- no forzar timestamps por palabra;
- threshold Auto 0.82;
- conservación de clusters acústicos sin texto;
- una sola llamada Sherpa con `adaptive=False`;
- sin retry solicitado/evitado;
- sin refinamiento de identidad V5.2;
- alineación por segmento;
- salida Auto marcada como estimación Ultra ambigua.

El worker persistente instala explícitamente el perfil `Ultrarrápida` dentro del proceso hijo `spawn`, evitando que Windows/PyInstaller caigan silenciosamente al perfil Equilibrado.

### PyInstaller Windows

`Windows Ultra executable #12`, run `34731116065`: **success**.

Artefacto GitHub Actions:

```text
VtT-Ultra-Windows
127.416.750 bytes
sha256:38b2bc64572f2de1f476db085154ff73d77552e6c25403c121ccacbe0a769821
expira: 12 de diciembre de 2026
```

El SHA anterior corresponde al ZIP/artefacto publicado por GitHub Actions, no a una firma Authenticode del `.exe` interior.

El workflow de build quedó nuevamente en ejecución manual (`workflow_dispatch`), sin trigger temporal de push.

## Qué medir en la prueba real

Registrar:

- carga del modelo;
- ASR;
- diarización;
- `sherpa_process_wall_seconds`;
- segmentación/embeddings/clustering internos si están disponibles;
- cantidad de clusters acústicos;
- cantidad de `Persona N` con texto;
- tiempo total;
- `processing_to_audio`;
- errores evidentes de cambio de voz dentro de un segmento.

Comparar siempre contra el mismo audio y el mismo PC.
