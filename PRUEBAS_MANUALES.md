# Pruebas manuales obligatorias — VtT V5.2

Este archivo registra lo que CI no puede sustituir y, separadamente, campañas reproducibles ya ejecutadas. Cada prueba manual debe anotar fecha, commit/artefacto, equipo, SO, configuración, resultado y evidencia no sensible.

Estados: `PENDIENTE`, `OK`, `FALLA`, `NO_APLICA`.

## 1. Escritorio — instalación y arranque

### Windows

- [ ] `run.bat` en ruta con espacios, paréntesis y tildes.
- [ ] Python 3.9+ sin privilegios de administrador.
- [ ] `.venv` antigua + cambio de `requirements.txt`: detectar hash distinto e instalar.
- [ ] `python run.py --repair` repara dependencias sin tocar transcripciones.
- [ ] ventana principal visible/redimensionable en la pantalla objetivo.
- [ ] migración V5.1→V5.2: una combinación no estándar se conserva como **Personalizado** sin cambiar modelo/perfiles.

### macOS/Linux

- [ ] arranque `run.sh`/`python3 run.py`.
- [ ] Linux: mensaje claro si faltan Tk/PortAudio.
- [ ] macOS: archivos normales sin BlackHole; loopback solo con dispositivo virtual.

## 2. Archivos y salidas

- [ ] MP3/WAV/M4A/OGG/FLAC.
- [ ] MP4/WEBM/MKV/MOV con audio.
- [ ] contenedor sin pista de audio rechazado antes de transcribir.
- [ ] archivo dañado + válido en mismo lote: éxito parcial y continuación.
- [ ] salida existente: `nombre (2)`, sin sobrescribir.
- [ ] cancelación con segmentos: salida parcial identificada.
- [ ] YouTube: salida final fuera del temporal eliminado al cerrar.

## 3. Grabación

### Micrófono

- [ ] dos grabaciones dentro del mismo segundo producen WAV distintos.
- [ ] medidor de nivel funciona.
- [ ] desconexión/cambio de dispositivo muestra error y no deja UI atrapada.
- [ ] disco lento/cola pendiente: WAV solo listo tras finalizar writer.

### Audio del sistema

Windows:

- [ ] loopback `soundcard` disponible.
- [ ] medidor responde al audio reproducido.
- [ ] WAV contiene el audio real.
- [ ] desconectar dispositivo conserva parcial y muestra error.

Linux/macOS:

- [ ] monitor PulseAudio/PipeWire cuando exista.
- [ ] BlackHole u otro dispositivo virtual en macOS cuando corresponda.

## 4. ASR y modos globales

Sobre el mismo audio registrar modelo, modo global, Perfil ASR, backend, Batch, Beam, carga, ASR seconds y procesamiento total.

- [ ] modo Rápido.
- [ ] modo Equilibrado.
- [ ] modo Preciso.
- [ ] Personalizado conserva los controles elegidos.
- [ ] GPU automática con CUDA compatible, si existe; confirmar fallback CPU.

No atribuir diferencias entre PCs distintos al perfil.

## 5. Diarización V5.2 en audio escuchable

Referencia: hablantes Auto, diarización Equilibrada y Word/JSON activos.

Registrar clusters sherpa, clusters tras identidad, hablantes con texto, clusters sin texto, perfil/shift, pasadas, precheck, selección identity-aware, wall por pasada, tiempo total, reutilización, embeddings/cache, sonda/detalle de turnos largos, reasignaciones y consistencia.

Cuando exista selección identity-aware, registrar también:

- `final_stage_wall_seconds`;
- `light_identity_wall_seconds`;
- `total_wall_seconds` / `identity_wall_seconds`.

Comprobar:

- [ ] una misma `Persona N` no representa evidentemente dos voces diferentes;
- [ ] intervenciones breves reales no desaparecen solo por duración;
- [ ] cambio sostenido dentro de un turno largo produce corte razonable;
- [ ] Auto ambiguo/reservado se presenta como estimación;
- [ ] manual N respeta el conteo solicitado;
- [ ] cluster acústico sin palabras sigue visible en el reporte;
- [ ] si el precheck evita segunda pasada, no introduce fusión audible incorrecta.

## 6. Reutilización/rendimiento

Sin cerrar VtT, procesar dos archivos con el mismo perfil y luego cambiar el perfil.

- [ ] segundo trabajo reutiliza modelos/motor cuando corresponde.
- [ ] registrar preparación/inicialización.
- [ ] cambio de `window_shift_ratio` reinicializa motor.
- [ ] comparar `processing_seconds` con duración sin tratar real-time como garantía.

## 7. Smoke acústico V5.2 — OK 09-09-2026

- [x] 2 hablantes → 2.
- [x] 4 hablantes → 4.
- [x] una pasada en ambos.
- [x] identidad habilitada.
- [x] PCM reutilizado desde diarización.
- [x] segundo trabajo reutiliza modelos/motor/extractor.
- [x] conteos correctos preservados.
- [x] workflow temporal eliminado.

Esto es smoke de conteo/reutilización, no DER/JER.

## 8. Benchmark ASR reproducible — OK 09-09-2026

Sobre `jfk.flac` público de OpenAI con timestamps por palabra:

```text
medium / Preciso      ~5.9 s · ~1.87x
medium / Equilibrado  ~4.6 s · ~2.38x
small  / Preciso      ~3.2 s · ~3.47x
small  / Equilibrado  ~1.5 s · ~7.45x
```

- [x] cuatro combinaciones ejecutan.
- [x] JSON/CSV generados en campaña.
- [x] similitud 1.000 frente a medium/Preciso en esa muestra.

No extrapolar al audio chileno del usuario ni a otro hardware.

## 9. Android físico ARM64

### Modelos/offline

- [ ] cortar primera descarga y confirmar reanudación.
- [ ] truncar/alterar modelo y comprobar rechazo/reacquisition.
- [ ] modo avión tras modelo válido.

### Ciclo de vida

- [ ] rotación.
- [ ] fondo/vuelta.
- [ ] cancelar en descarga, decodificación y transcripción.
- [ ] ACTION_SEND / ACTION_VIEW.
- [ ] TXT/SRT/edición.
- [ ] restaurar último documento tras reinicio de proceso.

### Audio por bloques

Probar 10, 60 y >90 minutos:

- [ ] sin OOM por PCM completo;
- [ ] timestamps globales crecientes;
- [ ] sin duplicación evidente en uniones ~88 s;
- [ ] sin pérdida de frase completa en empalme;
- [ ] cancelación intermedia;
- [ ] memoria, batería y temperatura.

## 10. APK/release

- [x] `Android APK #26`: build debug final verde.
- [x] artefacto debug y release rodante publicados por CI.
- [ ] instalar APK final en teléfono físico y completar flujo.
- [ ] con secrets de firma, producir/verificar APK firmado y `.sha256`.
- [ ] prueba de actualización de `android/RELEASE_SETUP.md`.

## 11. Empaquetado escritorio — OK 09-09-2026

`Desktop executables #8`, run `34407796151`, commit `5b2703d44f5196aa70769ae54ae6d945dab90d26`:

- [x] Windows PyInstaller.
- [x] Ubuntu PyInstaller.
- [x] macOS PyInstaller.
- [x] artefactos en los tres sistemas.
- [x] workflow restaurado a `workflow_dispatch` sin trigger temporal.
- [ ] abrir/usar cada ejecutable en hardware real.

Artefactos de CI:

```text
Windows  126.869.051 bytes  sha256:6d949ec154ed831631f99bf865c75a7261ade18ba546dfccd78ad828d6be8438
Ubuntu   186.195.924 bytes  sha256:3c38cc9f16e67fc919d41bc0d560b8d310e662528a65336c28d4175843594e9d
macOS    198.803.581 bytes  sha256:9f495afc5e0f11cac65fb188f5aa5764ceaa15324fe53ea6ab375b303f4f2890
```

## 12. Regresión de métricas de identidad — OK 09-09-2026

`Desktop checks #69`, run `34407637074`:

- [x] `vtt_diarization_v52_metrics.py` incluido en `py_compile`.
- [x] prueba de suma simple `final + light`.
- [x] valores negativos parciales no reducen el total válido.
- [x] dos llamadas `_light_identity` simuladas se acumulan completas.
- [x] `identity_wall_seconds` coincide con `total_wall_seconds`.
- [x] Windows, Ubuntu y macOS verdes.

Esta prueba valida contabilidad diagnóstica; no modifica ni valida calidad acústica.

## 13. Registro de campañas manuales

No marcar hardware como ejecutado por CI.

```text
Fecha:
Commit/artefacto:
Equipo/SO:
Pruebas ejecutadas:
Resultado:
Fallos/limitaciones:
Evidencia:
```
