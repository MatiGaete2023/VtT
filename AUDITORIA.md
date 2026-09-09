# AUDITORÍA DEL REPOSITORIO — VtT V5.2

**Actualizada:** 9 de septiembre de 2026  
**Rama:** `claude/voice-transcriber-multiplatform-6xifq1`

Esta auditoría registra el estado V5.2-performance y distingue lo comprobado por código/CI de lo que todavía necesita audio o hardware real.

## 1. Estado ejecutivo

### Escritorio

Estado: **V5.2 implementado y modularizado**.

- Python 3.9+.
- Entry point `desktop/vtt_main.py`.
- ASR: faster-whisper/CTranslate2.
- Diarización: sherpa-onnx.
- Modos globales Rápido/Equilibrado/Preciso/Personalizado.
- Auto estructural + precheck acústico acotado + selección identity-aware.
- Reutilización de modelos, motor, PCM y embeddings.
- Identidad rival-aware y sonda barata antes del escaneo detallado de turnos largos.
- Conteos separados de sherpa / identidad / texto.
- JSON maestro schema v7.
- Modelos sherpa protegidos por hashes auditados fijados en código.

### Android

Estado: **ASR local funcional; sin diarización del escritorio**.

- Kotlin + whisper.cpp/JNI, ARM64, minSdk 24.
- Progreso/cancelación nativa y trabajo en `TranscribeViewModel`.
- Modelos tiny/base/small con SHA-256 esperado antes de aceptar la primera descarga.
- Audios >5 min por bloques de 90 s + 2 s de solapamiento.
- JNI con handles opacos/shared_ptr; eliminada la fuga deliberada anterior.
- whisper.cpp fijado al commit `8a9ad7844d6e2a10cddf4b92de4089d7ac2b14a9`.

## 2. Hallazgos históricos corregidos

Continúan cerrados los defectos de captura de sistema Windows, pérdida de temporales, reinstalación de dependencias, bloqueo de Tk durante instalaciones, cierre inseguro del WAV, fallo silencioso de loopback, lectura de frecuencia, sobrescritura de exportaciones y ciclo de vida Android.

## 3. Hallazgos V5.2

### V52-01 [CORREGIDO] Segunda pasada Auto demasiado cara

En un caso real previo, la segunda pasada sherpa representó una fracción importante de la diarización total. V5.2 añade un precheck con presupuesto máximo de 18 embeddings y 3 por identidad. Si una sobredetección se consolida a una solución admisible, sin baja confianza y con penalización estructural acotada, evita la segunda pasada completa.

Si el precheck no es concluyente, sherpa sigue siendo la autoridad y se ejecuta el reintento.

### V52-02 [CORREGIDO] Selección de candidatos basada casi solo en estructura

Cuando dos candidatos Auto siguen ambiguos, V5.2 combina penalización estructural con consistencia acústica de identidad. La evidencia acústica complementa, no reemplaza, la diarización.

### V52-03 [CORREGIDO] Dos apariciones de una misma identidad podían pasar un umbral local y seguir siendo sospechosas

La comparación considera ahora similitud entre ambas apariciones y si una identidad rival explica significativamente mejor una de ellas.

### V52-04 [CORREGIDO] Similitud 1.00 engañosa con una sola muestra

Una identidad con una muestra se informa como insuficiente. Con dos muestras se reporta similitud directa entre apariciones y rival máximo; con más muestras se usan estadísticas de prototipo.

### V52-05 [CORREGIDO] Escaneo de turnos largos pagaba el costo detallado demasiado pronto

Se ejecuta primero una sonda de tres ventanas. Solo los turnos heterogéneos pasan al escaneo detallado.

### V52-06 [CORREGIDO] Conteo acústico y hablantes con texto se confundían

Los reportes separan:

1. clusters sherpa seleccionados;
2. clusters tras control de identidad;
3. hablantes con texto alineado;
4. clusters acústicos sin texto.

### V52-07 [CORREGIDO EN ESTA REVISIÓN] Migración de perfiles podía sobrescribir preferencias V5.1

La primera implementación V5.2 interpretaba la ausencia de `global_profile` como Equilibrado y podía cambiar silenciosamente modelo/ASR/diarización. La migración ahora reconoce un preset solo si los tres controles restaurados coinciden exactamente; cualquier combinación propia queda en Personalizado.

### V52-08 [CORREGIDO] Integridad de modelos sherpa dependía de TOFU

Los assets históricos de k2-fsa siguen mostrando `digest=null` en GitHub. Se descargaron dos veces desde los assets oficiales y los hashes coincidieron. VtT fija:

```text
segmentación archive  24615ee884c897d9d2ba09bb4d30da6bb1b15e685065962db5b02e76e4996488
segmentación model    220ad67ca923bef2fa91f2390c786097bf305bceb5e261d4af67b38e938e1079
embedding 3D-Speaker  1a331345f04805badbb495c775a6ddffcdd1a732567d5ec8b3d5749e3c7a5e4b
```

Se valida tamaño + hash antes de promover la descarga y se valida también el ONNX extraído. Son pins auditados por VtT, no digests publicados por upstream.

### V52-09 [CORREGIDO] GitHub Actions antiguas advertían runtime Node 20 deprecado

Los workflows relevantes se actualizaron a revisiones actuales fijadas por SHA, incluyendo checkout/setup-python/upload-artifact con runtime moderno. Se conserva el principio de no usar tags móviles como confianza final.

### V52-10 [CORREGIDO] Android: primera descarga de GGML no autenticada por catálogo

`ModelManager` contiene SHA-256 esperados para tiny/base/small y rechaza/promueve el archivo antes de convertirlo en modelo válido. Los sidecars locales quedan como mecanismo secundario.

### V52-11 [CORREGIDO] Android: PCM completo de audios largos

Para >5 min se usa `decodeRange()` y transcripción en ventanas de 90 s con 2 s de solapamiento. Se trasladan timestamps a la línea global y se deduplica el solape. La CI confirma compilación; la calidad de empalmes y consumo real siguen siendo pruebas de dispositivo.

### V52-12 [CORREGIDO] Handle JNI deliberadamente filtrado

El JNI usa identificadores opacos y un registro de `shared_ptr`. `nativeFree` puede retirar/liberar el Handle sin reintroducir use-after-free frente a `requestAbort`.

## 4. Verificaciones reproducibles V5.2

### Smoke acústico

Workflow temporal ejecutado dos veces y eliminado después.

Audios oficiales sherpa-onnx:

- 2 hablantes → 2 detectados;
- 4 hablantes → 4 detectados;
- una pasada en ambos ejemplos;
- reutilización de modelos, motor y extractor comprobada en el segundo trabajo;
- PCM de identidad reutilizado desde diarización.

Esto es un smoke de conteo/reutilización, no DER/JER.

### Benchmark ASR público

Sobre `jfk.flac` de OpenAI, en el runner utilizado:

```text
medium / Preciso      ~5.9 s · ~1.87x
medium / Equilibrado  ~4.6 s · ~2.38x
small  / Preciso      ~3.2 s · ~3.47x
small  / Equilibrado  ~1.5 s · ~7.45x
```

Las cuatro salidas tuvieron similitud textual 1.000 frente a medium/Preciso en esa muestra corta. No extrapolar estos tiempos ni esa similitud a español, otro hardware o al audio real del usuario.

### Android

La versión que incorporó hash de primera descarga, JNI seguro, `decodeRange()` y bloques largos compiló correctamente en `Android APK`. El job de release firmado se omite cuando no existe keystore, como está diseñado.

## 5. Límites que permanecen

No quedan como deuda de código los antiguos pendientes de bloques Android, pins de Actions, hashes esperados Android ni fuga del Handle JNI.

Sí requieren prueba externa/manual:

- calidad acústica exacta en el audio real del usuario;
- efecto real del precheck V5.2 sobre tiempo/calidad en audios con sobredetección;
- DER/JER con corpus temporalmente anotado;
- micrófono/loopback en hardware real;
- apertura y flujo de ejecutables PyInstaller en equipos reales;
- Android físico: empalmes de bloques largos, RAM, batería, temperatura y actualización firmada;
- GPU CUDA en hardware compatible.

## 6. Criterio de cierre

Código, CI, builds y documentación solo se consideran cerrados cuando la ejecución correspondiente está verde y no queda infraestructura temporal en el árbol. Las pruebas acústicas/hardware anteriores no deben convertirse en afirmaciones de certeza hasta que se ejecuten.
