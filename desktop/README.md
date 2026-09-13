# VtT — versión de escritorio V5.2.1

**Estado de esta guía:** 13 de septiembre de 2026.

VtT transcribe audio y video localmente en Windows, macOS y Linux. Whisper, diarización y verificación acústica de identidad se ejecutan en el equipo.

## 1. Requisitos e instalación

Requisito mínimo: **Python 3.9 o superior**.

En Windows:

1. Instala Python 3.9+ para el usuario; no se requieren privilegios de administrador en el flujo normal.
2. Entra en `desktop/`.
3. Ejecuta `run.bat`.

Alternativas: `python run.py`, `py run.py` o, en macOS/Linux, `./run.sh`/`python3 run.py`.

`run.py` crea `desktop/.venv`, instala `requirements.txt` y guarda su SHA-256 en `.venv/.deps_ok`. `--update` o `--repair` fuerza reparación. El entrypoint final es `vtt_main.py`.

## 2. Modos globales V5.2.1

Los presets son configuraciones completas: coordinan modelo ASR, perfil ASR, activación de hablantes, conteo Auto y perfil de diarización.

| Modo | Modelo | Perfil ASR | Hablantes | Diarización | Objetivo |
|---|---|---|---|---|---|
| Rápido | small | Rápido | Auto | Rápida 0.25 | prioriza velocidad CPU |
| Equilibrado | small | Equilibrado | Auto | Equilibrada 0.20 | recomendado; intenta quedar cerca/bajo tiempo real |
| Preciso | medium | Preciso | Auto | Equilibrada 0.20 | más precisión ASR y mayor presupuesto |
| Personalizado | libre | libre | libre | libre, incluida Precisa 0.10 | control manual |

**Precisa 0.10 ya no forma parte de un preset global.** Sigue disponible en Personalizado/avanzado. La prueba institucional mostró que su costo de embeddings sherpa era demasiado alto para uso habitual en CPU.

La migración desde V5.1 es conservadora: las firmas antiguas se reconocen como legado, pero una combinación que no coincide con un preset V5.2.1 completo queda en **Personalizado** y no se modifica silenciosamente.

## 3. Perfiles ASR

- **Rápido:** batching alto y búsqueda reducida.
- **Equilibrado:** compromiso recomendado.
- **Preciso:** mayor búsqueda; puede ser más lento.

CPU `int8` es la ruta segura. CUDA automática solo se usa si CTranslate2 la detecta utilizable. Cuando la diarización está activa, VtT solicita timestamps por palabra internamente porque son necesarios para la alineación palabra↔hablante.

`benchmark_asr.py` compara, sobre un mismo archivo, `medium/Preciso`, `medium/Equilibrado`, `small/Preciso` y `small/Equilibrado`. La similitud textual contra `medium/Preciso` es un indicador comparativo, no ground truth lingüístico.

## 4. Diarización

Perfiles:

- **Rápida:** `window_shift_ratio=0.25`.
- **Equilibrada:** `0.20`, recomendada.
- **Precisa:** `0.10`, alto costo CPU y solo avanzada/personalizada.

Número de hablantes: Auto o manual 2–8.

### Integridad de modelos

VtT descarga desde releases oficiales de k2-fsa:

- archive pyannote segmentation 3.0: 6.958.444 bytes;
- embedding 3D-Speaker: 39.593.761 bytes.

SHA-256 auditados por VtT:

```text
archive segmentación:
24615ee884c897d9d2ba09bb4d30da6bb1b15e685065962db5b02e76e4996488

model.onnx extraído:
220ad67ca923bef2fa91f2390c786097bf305bceb5e261d4af67b38e938e1079

embedding 3D-Speaker:
1a331345f04805badbb495c775a6ddffcdd1a732567d5ec8b3d5749e3c7a5e4b
```

La descarga se promueve a modelo válido solo si tamaño y hash coinciden. El ONNX extraído se valida por separado. Son pins auditados por VtT, no una firma upstream.

## 5. Auto V5.2.1 y presupuesto temporal

Flujo:

1. primera pasada sherpa;
2. análisis estructural;
3. si hay sobredetección/fragmentación, precheck acústico de bajo costo;
4. si el precheck resuelve el caso, se evita el reintento;
5. si no lo resuelve, V5.2.1 compara el tiempo ya consumido, el costo real de la primera pasada y el presupuesto del preset;
6. si una segunda pasada proyectada excedería el presupuesto, se conserva la primera solución y el resultado queda marcado como **ambiguo por presupuesto**;
7. si hay presupuesto, se permite el reintento y, cuando corresponde, selección identity-aware;
8. control final de identidad y trazabilidad.

El precheck mantiene máximo 18 embeddings y hasta 3 por identidad. El presupuesto temporal no interrumpe la primera pasada; evita repetir todo sherpa cuando el tiempo restante ya no alcanza.

Objetivos actuales de `processing_seconds`:

- Rápido: ~0.85× la duración del audio;
- Equilibrado: ~1.00×;
- Preciso: ~1.50×;
- Personalizado: sin límite automático.

Estos objetivos son políticas, no garantías de hardware.

## 6. Cancelación y recuperación

V5.2.1 usa una única excepción `DiarizacionCancelada` para los servicios V5/V5.1/V5.2. El pipeline la traduce siempre a la cancelación normal de la aplicación.

Al terminar ASR y antes de iniciar diarización, VtT escribe de forma atómica:

`<nombre>_ASR_RECUPERABLE.json`

Contiene texto y segmentos ya reconocidos. Se elimina después de un trabajo correcto y se conserva si la diarización falla o se cancela. Así un fallo posterior no obliga a perder el reconocimiento ya terminado.

La salida parcial tradicional también se mantiene cuando es posible.

## 7. Identidad V5.2

- turnos largos no forman prototipos completos por defecto;
- una voz breve no se elimina solo por duración;
- dos apariciones se evalúan por similitud directa y rival;
- una muestra única se informa como insuficiente;
- turnos largos usan primero una sonda de tres ventanas;
- embeddings y PCM se reutilizan dentro del job;
- modo manual conserva el conteo solicitado.

Las etiquetas alta/media/baja/insuficiente miden consistencia interna de agrupación. No identifican personas reales.

## 8. Conteos y alineación

V5.2.1 conserva magnitudes independientes:

- `raw_acoustic_clusters`: candidato sherpa seleccionado;
- `engine_identity_clusters`: resumen de identidad entregado por el motor;
- `identity_consistency_clusters`: conjunto explícito de IDs presentes en la auditoría de identidad;
- `identity_clusters_after_refinement`: conteo autoritativo usado en el reporte cuando existe el conjunto anterior;
- `text_assigned_speakers`: identidades que recibieron palabras;
- `unassigned_raw_ids`: identidades acústicas sin texto;
- `identity_count_mismatch`: diagnóstico cuando un resumen numérico del motor no coincide con el conjunto explícito.

Esto corrige la anomalía reproducida 8 / 9 / raw 5: el pipeline ya no reemplaza el conteo acústico por `len(speakers)`.

Cada palabra se cruza con turnos acústicos y un segmento Whisper puede dividirse internamente al cambiar la voz. Existe fallback por segmento cuando faltan palabras temporizadas.

## 9. Métricas finales

Se distinguen:

- `model_load_seconds`;
- `asr_seconds`;
- `diarization_seconds`;
- `export_seconds`;
- `overhead_seconds`;
- `report_generation_seconds`;
- `processing_seconds = ASR + diarización + exportación + overhead`;
- `end_to_end_seconds = carga modelo + procesamiento + generación de informes`.

El estado `performance` se recalcula desde estos valores finales. No se conserva un `within_realtime` calculado antes de exportar.

La contabilidad de identidad mantiene `final_stage_wall_seconds`, `light_identity_wall_seconds`, `total_wall_seconds` e `identity_wall_seconds`.

## 10. Exportaciones

- `.txt`: bloques legibles.
- `.md`: bloques/metadata.
- `.docx`: Word estructurado y diagnóstico.
- `.json`: fuente maestra **schema v8**.
- `.srt` / `.vtt`: segmentos técnicos.

El flujo V5.2.1 difiere JSON/DOCX hasta disponer de los tiempos funcionales finales. El Word se construye directamente en V5.2 y se guarda una sola vez; ya no se encadenan escritores V4→V5→V5.1→V5.2. Después solo se refresca el JSON final para persistir el tiempo de generación del informe y las métricas recalculadas.

Las salidas no sobreescriben silenciosamente familias existentes.

## 11. Worker y rendimiento institucional

El worker persistente reutiliza modelos/motor entre archivos compatibles. V5.2 evita segunda decodificación para identidad y comparte caché de embeddings.

Campaña institucional relevante:

- `medium + ASR Preciso + diarización Precisa 0.10`: diarización extremadamente lenta; embeddings sherpa dominaron el costo;
- `small + ASR Equilibrado` con diarización accidentalmente desactivada: 404 s de audio en ~164 s de ASR. Esa prueba demostró velocidad ASR pero no fue una prueba válida del preset completo;
- V5.2.1 corrige la causa: los presets globales ahora activan explícitamente `Hablantes: Auto`.

La próxima campaña comparable debe usar **Equilibrado + Auto** y registrar presupuesto, primera pasada, decisión de retry, tiempo por hilos y conteos por etapa.

## 12. Grabación, formatos y YouTube

Audio: `.mp3 .wav .m4a .ogg .flac .aac .wma .opus .aif .aiff`.

Video/contenedores: `.mp4 .webm .mkv .avi .mov .m4v .mpeg .mpg .3gp .ts .m2ts`.

PyAV verifica una pista de audio antes de un trabajo largo.

- Micrófono: `sounddevice`.
- Loopback Windows: `soundcard`/WASAPI.
- Linux: PulseAudio/PipeWire cuando existe.
- macOS: loopback requiere dispositivo virtual como BlackHole.
- YouTube: descarga explícita mediante `yt-dlp`.

## 13. Privacidad

ASR, diarización e identidad son locales. La red se usa para dependencias, primera descarga de modelos, YouTube explícito y CI/build. No hay telemetría ni analytics.

## 14. Verificación automatizada

`Desktop checks` ejecuta `py_compile` y `pytest` en Windows, macOS y Ubuntu. V5.2.1 añade regresiones de:

- excepción de cancelación compartida;
- traducción de cancelación en pipeline;
- checkpoint ASR recuperable;
- reproducción del conteo 8/10/9/raw5 sin colapsar magnitudes;
- recálculo de performance final;
- `processing_seconds` vs `end_to_end_seconds`;
- un solo `Document.save()` por DOCX V5.2;
- presets completos y migración legacy;
- presupuesto temporal Auto.

La campaña acústica con audios oficiales sherpa sigue siendo smoke de conteo/reutilización, no DER/JER. `Desktop executables` construye PyInstaller para Windows, macOS y Ubuntu.

## 15. Problemas frecuentes

- **Python no se reconoce:** instala Python 3.9+ para el usuario y prueba `py run.py`.
- **Venv dañada:** `python run.py --repair`.
- **Primera transcripción lenta:** puede estar descargando Whisper.
- **Primera diarización lenta:** descarga/verifica modelos y crea motor.
- **Precisa 0.10 muy lenta:** usa Equilibrada; 0.10 es avanzada.
- **Auto omitió segunda pasada:** revisa el campo de presupuesto; el resultado debe aparecer como ambiguo si la omisión fue temporal.
- **ASR_RECUPERABLE permanece:** una etapa posterior no terminó correctamente; conserva trabajo útil.
- **Auto muestra reservas/ambigüedad:** revisa voces o fija N si lo conoces.
- **Un archivo se rechaza:** no existe pista de audio decodificable.

Las pruebas de hardware y calidad acústica permanecen en `../PRUEBAS_MANUALES.md`.