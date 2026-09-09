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

Referencia recomendada:

- modo global Equilibrado o Personalizado;
- hablantes Auto;
- diarización Equilibrada;
- Word/JSON activos.

Registrar:

- clusters sherpa seleccionados;
- clusters tras identidad;
- hablantes con texto y clusters sin texto;
- perfil/Window shift;
- pasadas Auto;
- precheck, tiempo y si evitó segunda pasada;
- selección identity-aware si se utilizó;
- wall por pasada;
- tiempo total de diarización;
- reutilización de worker/modelos/motor/PCM;
- embeddings y caché;
- sonda/detalle de turnos largos;
- reasignaciones;
- consistencia global y por Persona.

Comprobar:

- [ ] una misma `Persona N` no representa evidentemente dos voces diferentes;
- [ ] intervenciones breves reales no desaparecen solo por duración;
- [ ] cambio sostenido dentro de un turno largo produce corte razonable cuando corresponde;
- [ ] Auto ambiguo/reservado se presenta como estimación;
- [ ] manual N respeta el conteo solicitado;
- [ ] un cluster acústico sin palabras aparece como tal y no desaparece del reporte;
- [ ] si el precheck evita segunda pasada, la reducción de tiempo no introduce una fusión audible incorrecta.

## 6. Reutilización/rendimiento

Sin cerrar VtT:

1. transcribir un archivo con diarización;
2. transcribir otro con el mismo perfil.

- [ ] segundo trabajo indica reutilización de modelos/motor.
- [ ] registrar preparación/inicialización.
- [ ] cambiar perfil de diarización y comprobar reinicialización al cambiar `window_shift_ratio`.
- [ ] comparar `processing_seconds` con duración; tratar real-time como objetivo medido, no garantía.

## 7. Smoke acústico reproducible V5.2 — OK 09-09-2026

Audios oficiales:

- `1-two-speakers-en.wav` → 2;
- `0-four-speakers-zh.wav` → 4.

Campaña V5.2, repetida durante el cierre:

- [x] 2 → 2.
- [x] 4 → 4.
- [x] una pasada en ambos casos.
- [x] verificación de identidad habilitada.
- [x] PCM reutilizado desde diarización para identidad.
- [x] segundo trabajo reutiliza modelos/motor/extractor.
- [x] la capa V5.2 no altera conteos correctos.
- [x] workflow temporal eliminado al terminar.

Esto valida conteo/reutilización en dos muestras conocidas; no es DER/JER.

## 8. Benchmark ASR reproducible — OK 09-09-2026

`benchmark_asr.py` se ejecutó sobre el `jfk.flac` público de OpenAI con timestamps por palabra:

```text
medium / Preciso      ~5.9 s · ~1.87x
medium / Equilibrado  ~4.6 s · ~2.38x
small  / Preciso      ~3.2 s · ~3.47x
small  / Equilibrado  ~1.5 s · ~7.45x
```

- [x] las cuatro combinaciones ejecutan.
- [x] JSON/CSV del benchmark generados en la campaña temporal.
- [x] similitud textual 1.000 contra medium/Preciso en esa muestra.

No usar estos números como estimación del audio chileno del usuario ni de otro hardware.

## 9. Android físico ARM64

### Modelos/offline

- [ ] primera descarga tiny/base; cortar red y confirmar reanudación.
- [ ] alterar/truncar un modelo local y comprobar que se rechaza y reacquire.
- [ ] modo avión después de modelo válido y transcribir archivo local.

### Ciclo de vida

- [ ] rotar durante transcripción.
- [ ] enviar app al fondo y volver.
- [ ] cancelar durante descarga, decodificación y transcripción.
- [ ] ACTION_SEND.
- [ ] ACTION_VIEW.
- [ ] editar texto, TXT y SRT.
- [ ] reiniciar proceso y restaurar último documento.

### Audio por bloques

Probar al menos 10, 60 y >90 minutos:

- [ ] no existe OOM por materializar el audio completo.
- [ ] timestamps globales permanecen crecientes.
- [ ] no se observa duplicación evidente en las uniones cada ~88 s.
- [ ] no se pierde una frase completa en el empalme.
- [ ] cancelar en un bloque intermedio detiene el proceso.
- [ ] registrar pico aproximado de memoria.
- [ ] registrar batería y temperatura.

La CI solo verifica que la implementación compile; estas condiciones requieren dispositivo/audio real.

## 10. APK/release

- [x] implementación Android de hashes/JNI/bloques compila en CI.
- [ ] instalar el APK final en teléfono físico y completar flujo.
- [ ] con secrets de firma, `assembleRelease` produce APK firmado y `.sha256`.
- [ ] ejecutar prueba de actualización de `android/RELEASE_SETUP.md` antes de distribuir como actualización.

## 11. Empaquetado de escritorio

La versión V5.1 tuvo PyInstaller verde en los tres sistemas. Para V5.2:

- [ ] Windows PyInstaller final.
- [ ] Ubuntu PyInstaller final.
- [ ] macOS PyInstaller final.
- [ ] artefactos presentes.
- [ ] workflow vuelve a `workflow_dispatch` sin trigger temporal.
- [ ] abrir/usar ejecutable en hardware real (independiente del build CI).

## 12. Registro de campañas manuales

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
