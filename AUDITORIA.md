# AUDITORÍA DEL REPOSITORIO — VtT V5.2.1

**Actualizada:** 13 de septiembre de 2026  
**Rama:** `claude/voice-transcriber-multiplatform-6xifq1`  
**Estado:** **CORRECCIONES DE INTEGRACIÓN V5.2.1 IMPLEMENTADAS Y CI MULTIPLATAFORMA VERDE**

Esta auditoría distingue lo comprobado por código/CI de lo que todavía necesita audio o hardware real.

## 1. Estado ejecutivo

### Escritorio

Estado: **V5.2.1 implementado**.

- Python 3.9+; entrypoint `desktop/vtt_main.py`.
- ASR: faster-whisper/CTranslate2.
- Diarización: sherpa-onnx.
- Presets globales completos Rápido/Equilibrado/Preciso y modo Personalizado.
- Los tres presets activan hablantes Auto; Equilibrado es la recomendación general.
- Preciso usa ASR `medium/Preciso` pero diarización **Equilibrada 0.20**; `Precisa 0.10` queda avanzada/personalizada.
- Auto estructural + precheck acústico + selección identity-aware + presupuesto temporal antes de repetir Sherpa.
- Reutilización de modelos, motor, PCM y embeddings.
- Alineación palabra↔hablante con división interna de segmentos.
- Conteos sherpa / identidad auditada / texto separados.
- Cancelación unificada y checkpoint ASR recuperable antes de diarización.
- Métricas finales distinguen procesamiento, generación de informes y espera extremo a extremo.
- JSON maestro schema v8.
- DOCX V5.2 directo, sin cadena de nueve guardados.
- Modelos sherpa protegidos por hashes auditados.
- `Desktop checks #91`, run `34729633409`: **99 pruebas verdes en Windows/macOS/Ubuntu**.
- PyInstaller V5.2.1 se ejecutó posteriormente como `Desktop executables #10`; su resultado se registra al cerrar esta auditoría.

### Android

Estado sin cambios funcionales en V5.2.1: ASR local funcional y build previamente verde; sin diarización desktop.

- Kotlin + whisper.cpp/JNI, ARM64, minSdk 24.
- Modelos tiny/base/small con SHA-256 esperado.
- Audios >5 min por bloques de 90 s + 2 s de solapamiento.
- JNI con handles opacos/shared_ptr.
- whisper.cpp fijado a `8a9ad7844d6e2a10cddf4b92de4089d7ac2b14a9`.

## 2. Hallazgos históricos corregidos

Continúan cerrados los defectos históricos de captura, temporales, dependencias, UI bloqueada, WAV incompleto, loopback, sobrescrituras, alineación por segmento, conteos Auto iniciales, identidad y ciclo de vida Android. Los módulos V4/V5/V5.1 permanecen porque forman la cadena de herencia activa.

## 3. Hallazgos V5.2 previos

Se mantienen como corregidos:

- precheck acústico de bajo costo;
- selección identity-aware;
- identidad rival-aware para dos apariciones;
- una muestra no se presenta como similitud 1.00 útil;
- sonda de turnos largos antes de escaneo detallado;
- integridad SHA-256 de modelos sherpa y Android;
- Actions fijadas por SHA;
- Android por bloques;
- eliminación de fuga Handle JNI;
- contabilidad `identity_wall_seconds` completa;
- rótulos Word V5.2 correctos;
- filtros de CI para Markdown;
- keystore Android reclasificado como dependencia externa.

## 4. Hallazgos V5.2.1 reproducidos y corregidos

### V521-01 [CORREGIDO] Excepción de cancelación incompatible entre servicio y pipeline

El pipeline V5 capturaba la clase de cancelación del servicio V5, mientras el servicio activo V5.2 declaraba otra clase independiente. Una cancelación durante diarización podía caer en la ruta de error y perder la semántica de cancelación normal.

**Corrección:** `desktop/vtt_diarization_errors.py` define una única `DiarizacionCancelada`, importada por servicios V5/V5.1/V5.2 y por el pipeline. Se añadió regresión que verifica identidad de clase y traducción a `transcriptor_whisper.Cancelado`.

### V521-02 [CORREGIDO] Trabajo ASR perdido si falla/cancela diarización

Antes de iniciar diarización se genera atómicamente `<stem>_ASR_RECUPERABLE.json` con texto y segmentos ya reconocidos. Se elimina al completar correctamente y se conserva ante fallo/cancelación. La salida parcial tradicional sigue intentándose.

Esto reduce el costo de recuperación: una etapa acústica posterior no obliga a repetir Whisper.

### V521-03 [CORREGIDO] Conteo acústico sustituido por hablantes con texto

`vtt_pipeline_v5.py` sobrescribía `meta["detected_speakers"]` con `len(speakers)` tras la alineación. V5.2 podía interpretar luego ese valor textual como identidad acústica.

**Corrección:** se conservan por separado:

- candidato sherpa seleccionado;
- conteo de identidad informado por el motor;
- conjunto explícito de IDs de `identity_consistency`;
- hablantes con texto;
- IDs acústicos sin texto;
- IDs de texto ausentes del audit de identidad;
- indicador de mismatch.

La regresión reproduce explícitamente un escenario **8 sherpa / 10 identidades auditadas / 9 con texto / raw 5 sin texto** y comprueba que ninguna magnitud sea colapsada.

### V521-04 [CORREGIDO] `performance` podía quedar obsoleto después de exportar

El estado de rendimiento podía haberse calculado antes de conocer tiempos definitivos y conservar `within_realtime=true` aunque el total final ya excediera el audio.

**Corrección:** `vtt_reporting.cerrar_metricas()` recalcula siempre los derivados; V5.2.1 reconstruye `performance` desde métricas finales. La regresión parte deliberadamente de un `performance` falso y verifica que JSON lo reemplace.

### V521-05 [CORREGIDO] Definición incompleta de espera percibida

Ahora se distinguen:

- `processing_seconds = ASR + diarización + exportación + overhead`;
- `report_generation_seconds`;
- `end_to_end_seconds = carga modelo + processing + generación de informes`.

El objetivo de tiempo real del preset usa `processing_seconds`; la espera extremo a extremo queda disponible separadamente.

### V521-06 [CORREGIDO] Word se guardaba repetidamente

El recorrido heredado podía guardar Word múltiples veces porque cada writer versionado llamaba al anterior y el pipeline regeneraba informes.

**Corrección:** V5.2.1 difiere JSON/DOCX hasta el cierre funcional y `vtt_reporting_v52.escribir_docx_detallado()` construye el documento directamente. La regresión instrumenta `Document.save()` y exige exactamente **un guardado**.

Después del informe final solo se refresca JSON para persistir tiempos/recalcular performance; Word no se reabre.

### V521-07 [CORREGIDO] Preset global no activaba realmente diarización

La prueba institucional del 12/09/2026 mostró `Modo global: Equilibrado` junto a `Hablantes: No`. El preset modificaba modelo/perfiles, pero no `v_diarizar` ni `v_num_speakers`.

**Corrección:** Rápido, Equilibrado y Preciso son ahora configuraciones completas y fuerzan `Hablantes: Auto`. Personalizado mantiene libertad manual. Cambiar un componente sale del preset a Personalizado.

### V521-08 [CORREGIDO] Precisa 0.10 dentro del preset Preciso era impráctica en CPU institucional

La campaña institucional con `medium + Preciso + Precisa 0.10` mostró costo prohibitivo de embeddings sherpa. V5.2.1 cambia el preset **Preciso** a diarización **Equilibrada 0.20**. `Precisa 0.10` no se elimina: permanece disponible en Personalizado.

### V521-09 [CORREGIDO] Auto podía pagar una segunda pasada sin límite temporal

`vtt_performance.py` antes solo evaluaba resultados. Ahora los presets poseen `target_processing_ratio` y calculan un presupuesto wall de diarización una vez terminado ASR.

Tras la primera pasada + precheck, el motor proyecta otra pasada utilizando el wall real de la primera. Si la proyección excede el presupuesto, omite el retry, conserva la primera solución y la validación queda como `estimacion_ambigua_presupuesto`.

No se interrumpe la primera pasada ni se promete tiempo real: es un freno a repetir un trabajo ya incompatible con el objetivo temporal.

### V521-10 [ACLARADO] Whisper ya reutilizaba modelo

No se añadió otra caché. `_worker_vtt` conserva `self.modelo` mientras `(modelo, device, compute)` no cambie. Los 19:13 observados en una primera prueba no se atribuyen a “cargar siempre Whisper”. La prueba posterior small/Equilibrado mostró carga ~12 s.

## 5. Evidencia automatizada V5.2.1

### Desktop checks #91

Run `34729633409`, commit `e35c1270b579964d4e9062dae929e7742c374c63`: **success**.

- Windows: success.
- Ubuntu: success.
- macOS: success.
- `py_compile`: success.
- `pytest`: **99 passed**.

Nuevas regresiones cubren cancelación compartida, checkpoint ASR, conteos 8/10/9/raw5, métricas finales/end-to-end, performance stale, un solo guardado DOCX, presets completos y presupuesto Auto.

### Smoke acústico histórico V5.2

- 2 hablantes → 2.
- 4 hablantes → 4.
- una pasada en ambos.
- reutilización de modelos/motor/extractor.

Sigue siendo smoke de conteo/reutilización, no DER/JER.

## 6. Campañas institucionales que motivaron V5.2.1

### Preciso + diarización Precisa 0.10

Audio 404 s. En el PC institucional se observaron aproximadamente:

- ASR: 324 s;
- diarización: 785 s;
- sherpa process: 513 s;
- embeddings internos: 474 s;
- segunda pasada: 216 s.

Conclusión: 0.10 no es viable como perfil global habitual en ese hardware.

### Small + ASR Equilibrado

El mismo audio, con la diarización **accidentalmente desactivada por el defecto del preset**, tomó aproximadamente:

- carga modelo: 12 s;
- ASR: 164 s;
- procesamiento: 165 s;
- 2.45× tiempo real.

Esta campaña valida velocidad ASR, no diarización. V5.2.1 impide repetir esa ambigüedad de UI porque Equilibrado activa Auto explícitamente.

## 7. Límites vigentes

Requieren nueva evidencia externa/manual:

- mismo audio institucional con **Equilibrado + Auto realmente activo**;
- efecto del presupuesto temporal sobre calidad cuando omite retry;
- comparar `VTT_DIAR_THREADS` 1/2/4 en el mismo equipo/configuración;
- DER/JER con corpus anotado;
- micrófono/loopback y CUDA reales;
- apertura de ejecutables PyInstaller en hardware objetivo;
- Android físico: empalmes largos, RAM, batería, temperatura y actualización firmada.

No atribuir la lentitud institucional a antivirus, CPU u ONNX Runtime sin medición controlada.

## 8. Resultado actual

V5.2.1 corrige los defectos reproducibles de integración antes de una nueva campaña acústica. La prioridad siguiente no es añadir más heurísticas: es medir **Equilibrado + Auto** en el mismo PC/audio con métricas ahora confiables y, luego, comparar 1/2/4 hilos si la diarización sigue dominando.