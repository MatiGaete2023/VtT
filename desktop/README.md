# VtT — versión de escritorio V5.2-performance

**Estado de esta guía:** 9 de septiembre de 2026.

VtT transcribe audio y video localmente en Windows, macOS y Linux. Whisper, diarización y verificación acústica de identidad se ejecutan en el equipo.

## 1. Requisitos e instalación

Requisito mínimo: **Python 3.9 o superior**.

En Windows:

1. Instala Python 3.9+ para el usuario; no se requieren privilegios de administrador en el flujo normal.
2. Entra en `desktop/`.
3. Ejecuta `run.bat`.

Alternativas: `python run.py`, `py run.py` o, en macOS/Linux, `./run.sh`/`python3 run.py`.

`run.py` crea `desktop/.venv`, instala `requirements.txt` y guarda su SHA-256 en `.venv/.deps_ok`. `--update` o `--repair` fuerza reparación. El entrypoint final es `vtt_main.py`.

## 2. Modos globales V5.2

V5.2 añade un selector de alto nivel que coordina modelo ASR, perfil ASR y perfil de diarización:

| Modo | Modelo | Perfil ASR | Diarización | Uso |
|---|---|---|---|---|
| Rápido | small | Rápido | Rápida | prioriza velocidad CPU |
| Equilibrado | small | Equilibrado | Equilibrada | recomendado para uso habitual |
| Preciso | medium | Preciso | Precisa | mayor costo para casos donde se justifica |
| Personalizado | no impone | no impone | no impone | conserva controles individuales |

La migración desde V5.1 es conservadora: si una configuración anterior no coincide exactamente con un preset V5.2, se abre como **Personalizado** y no se sobreescribe silenciosamente.

## 3. Perfiles ASR

- **Rápido:** batching alto y búsqueda reducida.
- **Equilibrado:** compromiso recomendado.
- **Preciso:** mayor búsqueda; puede ser más lento.

CPU `int8` es la ruta segura. CUDA automática solo se usa si CTranslate2 la detecta utilizable. Cuando la diarización está activa, VtT solicita timestamps por palabra internamente porque son necesarios para la alineación palabra↔hablante.

Se incluye `benchmark_asr.py` para comparar, sobre un mismo archivo, `medium/Preciso`, `medium/Equilibrado`, `small/Preciso` y `small/Equilibrado`. La similitud textual contra `medium/Preciso` es solo un indicador comparativo: no reemplaza ground truth lingüístico.

## 4. Diarización

Perfiles:

- **Rápida:** `window_shift_ratio=0.25`.
- **Equilibrada:** `0.20`, recomendada.
- **Precisa:** `0.10`, alto costo CPU.

Número de hablantes: Auto o manual 2–8.

### Integridad de modelos

VtT descarga desde releases oficiales de k2-fsa:

- archive pyannote segmentation 3.0: 6.958.444 bytes;
- embedding 3D-Speaker: 39.593.761 bytes.

Los assets históricos no entregan `digest` en la API de GitHub. Para no depender del TOFU anterior, VtT fija los SHA-256 reproducidos en dos descargas independientes de los assets oficiales el 9 de septiembre de 2026:

```text
archive segmentación:
24615ee884c897d9d2ba09bb4d30da6bb1b15e685065962db5b02e76e4996488

model.onnx extraído:
220ad67ca923bef2fa91f2390c786097bf305bceb5e261d4af67b38e938e1079

embedding 3D-Speaker:
1a331345f04805badbb495c775a6ddffcdd1a732567d5ec8b3d5749e3c7a5e4b
```

La descarga se promueve a modelo válido solo si tamaño y hash coinciden. El ONNX extraído se valida por separado. Estos son **pins auditados por VtT**, no una firma publicada por upstream.

## 5. Auto V5.2-performance

Auto mantiene el análisis estructural V4/V5, pero V5.2 agrega una ruta de bajo costo antes de repetir sherpa completo.

Flujo:

1. primera pasada con umbral balanceado;
2. análisis de cantidad, dominancia, duración de turnos, microclusters y frecuencia de cambios;
3. si existe sobredetección/fragmentación, precheck acústico acotado con embeddings;
4. si el precheck consolida la solución de forma segura, se evita la segunda pasada completa;
5. si no es concluyente, se ejecuta el reintento sherpa;
6. cuando ambos candidatos siguen ambiguos, se combina penalización estructural con consistencia de identidad para elegir;
7. una verificación final registra trazabilidad y confianza.

El precheck está deliberadamente presupuestado: máximo 18 embeddings y hasta 3 por identidad. No sustituye sherpa por un clasificador biométrico.

## 6. Identidad V5.2

V5.2 conserva los principios V5.1 y corrige puntos ciegos:

- turnos largos no forman prototipos por defecto;
- una voz breve no se elimina solo por duración;
- una identidad con dos apariciones se evalúa por similitud entre ambas **y** por cuánto mejor la explica una identidad rival;
- una muestra única se informa como insuficiente, sin presentar la similitud trivial del vector consigo mismo como evidencia;
- un turno largo recibe primero una sonda de tres ventanas; solo si resulta heterogéneo pasa al escaneo detallado;
- embeddings y PCM se reutilizan dentro del job para reducir costo;
- en modo manual se respeta el número fijado por el usuario.

Las etiquetas alta/media/baja/insuficiente miden consistencia interna de la agrupación. No identifican personas reales.

## 7. Conteos y alineación

V5.2 separa tres magnitudes que antes podían confundirse:

- **clusters sherpa seleccionados**;
- **clusters tras control de identidad**;
- **hablantes con texto asignado**.

Un cluster acústico sin palabras alineadas no desaparece de la trazabilidad: queda identificado como cluster sin texto en JSON/Word.

Cada palabra se cruza con los turnos acústicos. Un segmento Whisper puede dividirse internamente si cambia la voz. Existe fallback por segmento cuando faltan palabras temporizadas.

## 8. Worker y rendimiento

El worker persistente permite reutilizar modelos y motor entre archivos compatibles. V5.2 además evita una segunda decodificación para identidad y comparte un caché de embeddings durante precheck, selección y validación final.

JSON/DOCX registra, según disponibilidad:

- carga del modelo Whisper;
- ASR;
- diarización total;
- preparación/reutilización del motor;
- wall por cada pasada sherpa;
- timers internos sherpa cuando el backend los expone/captura;
- precheck y si evitó el reintento;
- tiempo/llamadas de embeddings de identidad;
- conteos por etapa;
- presupuesto `processing_seconds <= audio_seconds`.

El objetivo de tiempo real es un indicador por equipo, no una garantía universal.

## 9. Exportaciones

- `.txt`: bloques legibles.
- `.md`: bloques/metadata.
- `.docx`: Word estructurado y diagnóstico.
- `.json`: fuente maestra **schema v7**.
- `.srt` / `.vtt`: segmentos técnicos.

Las exportaciones no sobreescriben silenciosamente una familia existente. El DOCX no corrige semánticamente el ASR: nombres propios, cifras y frases dudosas requieren revisión humana cuando la exactitud sea importante.

## 10. Grabación, formatos y YouTube

Audio: `.mp3 .wav .m4a .ogg .flac .aac .wma .opus .aif .aiff`.

Video/contenedores: `.mp4 .webm .mkv .avi .mov .m4v .mpeg .mpg .3gp .ts .m2ts`.

PyAV verifica que exista una pista de audio antes de iniciar un trabajo largo.

- Micrófono: `sounddevice`.
- Loopback Windows: `soundcard`/WASAPI.
- Linux: monitores PulseAudio/PipeWire cuando existen.
- macOS: loopback requiere un dispositivo virtual como BlackHole.
- YouTube: descarga explícita mediante `yt-dlp`; FFmpeg es opcional para mejorar esa descarga.

## 11. Privacidad

ASR, diarización e identidad son locales. La red se usa para dependencias, primera descarga de modelos, descarga explícita de YouTube y CI/build. No hay telemetría ni analytics.

## 12. Verificación automatizada

`Desktop checks` ejecuta `py_compile` y `pytest` en Windows, macOS y Ubuntu. La suite incluye V5.2, migración de perfiles, identidad rival-aware, precheck Auto, conteos separados, reporting e integridad de modelos.

La campaña reproducible V5.2 con audios oficiales sherpa-onnx confirmó:

- 2 hablantes → 2;
- 4 hablantes → 4;
- una pasada en ambos ejemplos;
- reutilización de modelos/motor/extractor en el segundo trabajo.

El benchmark público `jfk.flac` confirmó que las cuatro combinaciones ASR se ejecutan; no constituye una evaluación de precisión para español ni del audio real del usuario.

`Desktop executables` construye PyInstaller para Windows, macOS y Ubuntu. Las Actions se fijan por SHA.

## 13. Problemas frecuentes

- **Python no se reconoce:** instala Python 3.9+ para el usuario y prueba `py run.py`.
- **Venv dañada:** `python run.py --repair`.
- **Primera transcripción lenta:** puede estar descargando Whisper.
- **Primera diarización lenta:** descarga/verifica los modelos y crea el motor.
- **Precisa muy lenta:** usa Equilibrada.
- **Auto muestra reservas/ambigüedad:** revisa las voces o fija N si lo conoces.
- **Un archivo se rechaza:** no se encontró una pista de audio decodificable.
- **Captura del sistema no aparece:** revisa el backend del SO; macOS requiere dispositivo virtual.

Las pruebas de hardware y de calidad acústica permanecen en `../PRUEBAS_MANUALES.md`.
