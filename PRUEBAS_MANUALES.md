# Pruebas manuales obligatorias — VtT V5.2.1

Este archivo registra lo que CI no puede sustituir y, separadamente, campañas reproducibles ya ejecutadas. Cada prueba manual debe anotar fecha, commit/artefacto, equipo, SO, configuración, resultado y evidencia no sensible.

Estados: `PENDIENTE`, `OK`, `FALLA`, `NO_APLICA`.

## 1. Escritorio — instalación y arranque

### Windows

- [ ] `run.bat` en ruta con espacios, paréntesis y tildes.
- [ ] Python 3.9+ sin privilegios de administrador.
- [ ] `.venv` antigua + cambio de `requirements.txt`: detectar hash distinto e instalar.
- [ ] `python run.py --repair` repara dependencias sin tocar transcripciones.
- [ ] ventana principal visible/redimensionable en la pantalla objetivo.
- [ ] migración V5.1→V5.2.1: una combinación no estándar se conserva como **Personalizado** sin cambiar controles.

### macOS/Linux

- [ ] arranque `run.sh`/`python3 run.py`.
- [ ] Linux: mensaje claro si faltan Tk/PortAudio.
- [ ] macOS: archivos normales sin BlackHole; loopback solo con dispositivo virtual.

## 2. Presets globales V5.2.1

Antes de iniciar, confirmar visualmente que el resumen efectivo coincide con el preset:

- [ ] **Rápido:** small + ASR Rápido + Hablantes Auto + diarización Rápida 0.25.
- [ ] **Equilibrado:** small + ASR Equilibrado + Hablantes Auto + diarización Equilibrada 0.20.
- [ ] **Preciso:** medium + ASR Preciso + Hablantes Auto + diarización Equilibrada 0.20.
- [ ] **Personalizado:** modificar un componente y confirmar que el preset pasa a Personalizado.
- [ ] Precisa 0.10 solo es seleccionable/operativa mediante Personalizado.

La prueba institucional del 12/09/2026 que mostró `Modo global Equilibrado` + `Hablantes No` corresponde a V5.2 anterior y no debe repetirse con V5.2.1.

## 3. Archivos, cancelación y recuperación

- [ ] MP3/WAV/M4A/OGG/FLAC.
- [ ] MP4/WEBM/MKV/MOV con audio.
- [ ] contenedor sin pista de audio rechazado antes de transcribir.
- [ ] archivo dañado + válido en mismo lote: éxito parcial y continuación.
- [ ] salida existente: `nombre (2)`, sin sobrescribir.
- [ ] cancelar durante ASR: salida parcial cuando existan segmentos.
- [ ] cancelar durante diarización: debe registrarse como **cancelación**, no `archivo_fallido`.
- [ ] tras terminar ASR e iniciar diarización existe `<stem>_ASR_RECUPERABLE.json`.
- [ ] si diarización se cancela/falla, el checkpoint ASR permanece legible.
- [ ] si el trabajo termina correctamente, el checkpoint ASR se elimina.
- [ ] YouTube: salida final fuera del temporal eliminado al cerrar.

## 4. Métricas y exportación

En JSON final comprobar:

- [ ] `processing_seconds = asr + diarization + export + overhead`.
- [ ] `report_generation_seconds` existe por separado.
- [ ] `end_to_end_seconds = model_load + processing + report_generation`.
- [ ] `performance.within_realtime` coincide con `processing_seconds <= audio_seconds`.
- [ ] `performance.end_to_end_within_realtime` refleja la espera completa cuando corresponde.
- [ ] JSON final no conserva un estado `performance` anterior a la exportación.
- [ ] Word se genera una vez por salida final y abre correctamente.
- [ ] tiempos/labels visibles en Word son coherentes con JSON, salvo que el JSON es autoritativo para el tiempo de generación del propio informe.

## 5. ASR y precisión léxica

Sobre el mismo audio registrar modelo, preset, ASR, backend, Batch, Beam, carga y texto dudoso.

- [ ] small / Equilibrado.
- [ ] medium / Equilibrado si small pierde demasiada precisión.
- [ ] medium / Preciso solo cuando el costo se justifique.

No cambiar ASR y diarización a la vez cuando se intenta atribuir una mejora a un solo factor.

## 6. Diarización V5.2.1 en audio escuchable

Referencia inicial: **Equilibrado + Auto + Word/JSON**.

Registrar:

- clusters Sherpa seleccionados;
- `engine_identity_clusters`;
- `identity_consistency_clusters`;
- `identity_clusters_after_refinement`;
- hablantes con texto;
- IDs acústicos sin texto;
- `identity_count_mismatch`;
- perfil/shift/hilos;
- presupuesto Auto;
- pasadas y decisión de retry;
- precheck y selección identity-aware;
- wall por pasada;
- Sherpa segmentation/embedding/clustering cuando esté disponible;
- identidad final/ligera/total;
- tiempo completo/end-to-end.

Comprobar:

- [ ] una misma `Persona N` no representa evidentemente dos voces distintas;
- [ ] intervenciones breves reales no desaparecen solo por duración;
- [ ] cambio sostenido dentro de turno largo produce corte razonable;
- [ ] Auto ambiguo/reservado se presenta como estimación;
- [ ] manual N respeta el conteo solicitado;
- [ ] cluster acústico sin palabras sigue visible;
- [ ] si el presupuesto omite la segunda pasada, el estado es `estimacion_ambigua_presupuesto` o equivalente visible;
- [ ] si el precheck evita retry por evidencia acústica, no introduce una fusión audible incorrecta.

## 7. Campaña institucional prioritaria

Usar el mismo archivo de 6:44 que motivó V5.2.1 y el mismo PC institucional.

### 7.1 Equilibrado + Auto

- [ ] mantener VtT abierto durante la campaña;
- [ ] confirmar antes de iniciar: small / ASR Equilibrado / Auto / Equilibrada 0.20;
- [ ] registrar carga modelo y ASR;
- [ ] registrar `diarization_time_budget_seconds`;
- [ ] registrar primera pasada Sherpa;
- [ ] confirmar si el precheck resuelve o si se activa la regla de presupuesto;
- [ ] registrar si la segunda pasada fue ejecutada, evitada o omitida por presupuesto;
- [ ] revisar calidad de las etiquetas Persona N;
- [ ] comparar `processing_seconds` y `end_to_end_seconds` con 404 s de audio.

Referencia previa sin diarización: small/Equilibrado ≈164 s ASR. Con reserva de 5 s, el presupuesto orientativo de diarización para objetivo 1.0× es ≈235 s. Es una meta, no una garantía.

### 7.2 Hilos

Solo si diarización sigue dominando. Mantener idénticos audio/preset/modelos y variar exclusivamente:

- [ ] `VTT_DIAR_THREADS=1`.
- [ ] `VTT_DIAR_THREADS=2`.
- [ ] `VTT_DIAR_THREADS=4`.

No asumir que más hilos es más rápido. Registrar wall de Sherpa y sus embeddings.

## 8. Reutilización

Sin cerrar VtT, procesar dos trabajos compatibles:

- [ ] segundo trabajo reutiliza Whisper cuando modelo/backend no cambian;
- [ ] segundo trabajo reutiliza modelos/motor de diarización cuando corresponde;
- [ ] cambio de `window_shift_ratio` reinicializa motor;
- [ ] carga de modelo se distingue de processing/end-to-end.

## 9. Smoke acústico histórico — OK 09-09-2026

- [x] 2 hablantes → 2.
- [x] 4 hablantes → 4.
- [x] una pasada en ambos.
- [x] identidad habilitada.
- [x] PCM reutilizado desde diarización.
- [x] segundo trabajo reutiliza modelos/motor/extractor.

Es smoke de conteo/reutilización, no DER/JER.

## 10. Regresiones automáticas V5.2.1 — OK 13-09-2026

`Desktop checks #91`, run `34729633409`, commit `e35c1270b579964d4e9062dae929e7742c374c63`:

- [x] Windows, Ubuntu y macOS verdes.
- [x] `py_compile` verde.
- [x] **99 pruebas** pasan.
- [x] excepción de cancelación compartida.
- [x] traducción de cancelación en pipeline.
- [x] checkpoint ASR recuperable atómico.
- [x] reproducción 8 Sherpa / 10 identidad / 9 texto / raw5 sin colapsar conteos.
- [x] performance final recalculado.
- [x] processing vs end-to-end.
- [x] DOCX V5.2 con un solo `Document.save()`.
- [x] presets completos y compatibilidad legacy.
- [x] presupuesto temporal Auto.

## 11. Empaquetado escritorio V5.2.1 — OK 13-09-2026

`Desktop executables #10`, run `34729719142`, commit de build `73eb316d1b5ee21b4b0c50aa2590a53e0f7e3edb`: **success**.

Artefactos de GitHub Actions (digest del archivo de artefacto/ZIP):

```text
Windows  127.406.261 bytes  sha256:9fd75ca1c7fb9ffa92fb6db2930a332bdbc478cf6a1ce2f3b4af94745d914228
Ubuntu   186.939.422 bytes  sha256:459c7e853694c61a902e21c37506aecc6720c157f49ed834c27c4afafe556412
macOS    199.141.220 bytes  sha256:cdeca75e0177c0f834faa29bad1f69d58a40e52ce523bebab9718b000ce004d7
```

Expiran el 12 de diciembre de 2026.

- [x] PyInstaller Windows.
- [x] PyInstaller Ubuntu.
- [x] PyInstaller macOS.
- [x] trigger temporal retirado después de disparar el build.
- [ ] abrir/usar cada ejecutable en hardware real.

## 12. Grabación

### Micrófono

- [ ] dos grabaciones dentro del mismo segundo producen WAV distintos.
- [ ] medidor de nivel funciona.
- [ ] desconexión/cambio de dispositivo muestra error y no deja UI atrapada.

### Audio del sistema

Windows:

- [ ] loopback `soundcard` disponible.
- [ ] medidor responde al audio reproducido.
- [ ] WAV contiene audio real.

Linux/macOS:

- [ ] monitor PulseAudio/PipeWire cuando exista.
- [ ] BlackHole u otro dispositivo virtual en macOS cuando corresponda.

## 13. Android físico ARM64

- [ ] cortar primera descarga y confirmar reanudación.
- [ ] alterar modelo y comprobar rechazo/reacquisition.
- [ ] modo avión tras modelo válido.
- [ ] rotación/fondo/vuelta.
- [ ] cancelar descarga, decodificación y transcripción.
- [ ] ACTION_SEND / ACTION_VIEW.
- [ ] audio de 10, 60 y >90 min sin OOM.
- [ ] timestamps globales crecientes y empalmes sin duplicación/pérdida notable.
- [ ] memoria, batería y temperatura.

## 14. APK/release

Última campaña Android funcional previamente verificada: `Android APK #28`, run `34424903439`.

- [x] build debug CI verde.
- [x] artefacto y release rodante.
- [x] ausencia de keystore manejada según diseño.
- [ ] instalar APK en teléfono físico.
- [ ] producir/verificar release firmado cuando existan secrets.

## 15. Registro de campaña manual

```text
Fecha:
Commit/artefacto:
Equipo/SO:
Audio:
Preset/configuración:
Hilos:
Pruebas ejecutadas:
Tiempos:
Conteos:
Resultado acústico:
Fallos/limitaciones:
Evidencia:
```