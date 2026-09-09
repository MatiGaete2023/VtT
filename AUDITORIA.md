# AUDITORÍA DEL REPOSITORIO — VtT V5.2

**Actualizada:** 9 de septiembre de 2026  
**Rama:** `claude/voice-transcriber-multiplatform-6xifq1`  
**Estado:** **CIERRE DE CÓDIGO/CI/EMPAQUETADO VERIFICADO**

Esta auditoría registra el estado V5.2-performance y distingue lo comprobado por código/CI de lo que todavía necesita audio o hardware real.

## 1. Estado ejecutivo

### Escritorio

Estado: **V5.2 implementado, probado y empaquetado**.

- Python 3.9+.
- Entry point `desktop/vtt_main.py`.
- ASR: faster-whisper/CTranslate2.
- Diarización: sherpa-onnx.
- Modos globales Rápido/Equilibrado/Preciso/Personalizado.
- Auto estructural + precheck acústico acotado + selección identity-aware.
- Reutilización de modelos, motor, PCM y embeddings.
- Identidad rival-aware y sonda barata antes del escaneo detallado de turnos largos.
- Conteos separados de sherpa / identidad / texto.
- Métricas de identidad separadas en etapa final, evaluaciones ligeras y total acumulado.
- JSON maestro schema v7.
- Modelos sherpa protegidos por hashes auditados fijados en código.
- `Desktop checks #69`: verde en Windows/macOS/Ubuntu.
- `Desktop executables #8`: verde en Windows/macOS/Ubuntu.

### Android

Estado: **ASR local funcional y build final verde; sin diarización del escritorio**.

- Kotlin + whisper.cpp/JNI, ARM64, minSdk 24.
- Progreso/cancelación nativa y trabajo en `TranscribeViewModel`.
- Modelos tiny/base/small con SHA-256 esperado antes de aceptar la primera descarga.
- Audios >5 min por bloques de 90 s + 2 s de solapamiento.
- JNI con handles opacos/shared_ptr; eliminada la fuga deliberada anterior.
- whisper.cpp fijado al commit `8a9ad7844d6e2a10cddf4b92de4089d7ac2b14a9`.
- `Android APK #26`: build debug, artefacto y release rodante verdes; release firmado omitido por ausencia de keystore, según diseño.

## 2. Hallazgos históricos corregidos

Continúan cerrados los defectos de captura de sistema Windows, pérdida de temporales, reinstalación de dependencias, bloqueo de Tk durante instalaciones, cierre inseguro del WAV, fallo silencioso de loopback, lectura de frecuencia, sobrescritura de exportaciones y ciclo de vida Android.

## 3. Hallazgos V5.2

### V52-01 [CORREGIDO] Segunda pasada Auto demasiado cara

V5.2 añade un precheck con presupuesto máximo de 18 embeddings y 3 por identidad. Si una sobredetección se consolida a una solución admisible, sin baja confianza y con penalización estructural acotada, evita la segunda pasada completa. Si no es concluyente, sherpa sigue siendo la autoridad y se ejecuta el reintento.

### V52-02 [CORREGIDO] Selección de candidatos basada casi solo en estructura

Cuando dos candidatos Auto siguen ambiguos, V5.2 combina penalización estructural con consistencia acústica de identidad.

### V52-03 [CORREGIDO] Identidad con dos apariciones mal caracterizada

La comparación considera similitud entre ambas apariciones y si una identidad rival explica significativamente mejor una de ellas.

### V52-04 [CORREGIDO] Similitud 1.00 engañosa con una sola muestra

Una identidad con una muestra se informa como insuficiente. Con dos muestras se reporta similitud directa y rival máximo; con más muestras se usan estadísticas de prototipo.

### V52-05 [CORREGIDO] Escaneo largo demasiado costoso

Se ejecuta primero una sonda de tres ventanas. Solo los turnos heterogéneos pasan al escaneo detallado.

### V52-06 [CORREGIDO] Conteos mezclados

Los reportes separan clusters sherpa, clusters tras identidad, hablantes con texto y clusters acústicos sin texto.

### V52-07 [CORREGIDO EN AUDITORÍA] Migración de perfiles podía sobrescribir preferencias V5.1

La primera implementación interpretaba la ausencia de `global_profile` como Equilibrado. La migración ahora reconoce un preset solo si los tres controles restaurados coinciden exactamente; cualquier combinación propia queda en Personalizado. Se añadió prueba de regresión.

### V52-08 [CORREGIDO] Integridad de modelos sherpa dependía de TOFU

Los assets históricos de k2-fsa siguen mostrando `digest=null`. Dos descargas independientes desde los assets oficiales reprodujeron los mismos hashes y se auditó además el ONNX extraído:

```text
segmentación archive  24615ee884c897d9d2ba09bb4d30da6bb1b15e685065962db5b02e76e4996488
segmentación model    220ad67ca923bef2fa91f2390c786097bf305bceb5e261d4af67b38e938e1079
embedding 3D-Speaker  1a331345f04805badbb495c775a6ddffcdd1a732567d5ec8b3d5749e3c7a5e4b
```

VtT valida tamaño + hash antes de promover la descarga y valida el ONNX extraído. Son pins auditados por VtT, no digests publicados por upstream.

### V52-09 [CORREGIDO] GitHub Actions antiguas/runtime Node 20

Los workflows relevantes se actualizaron a revisiones actuales fijadas por SHA: checkout/setup-python/upload-artifact usan versiones con runtime moderno. Android conserva setup-java/setup-android/Gradle/release igualmente fijados por SHA.

### V52-10 [CORREGIDO] Android: primera descarga GGML sin catálogo

`ModelManager` contiene SHA-256 esperados para tiny/base/small y valida antes de promover el archivo.

### V52-11 [CORREGIDO] Android: PCM completo de audios largos

Para >5 min se usa `decodeRange()` y ventanas de 90 s con 2 s de solapamiento. La CI confirma compilación; empalmes/consumo real siguen siendo pruebas físicas.

### V52-12 [CORREGIDO] Handle JNI deliberadamente filtrado

El JNI usa identificadores opacos y registro `shared_ptr`; `nativeFree` puede retirar/liberar el Handle sin reintroducir use-after-free.

### V52-13 [CORREGIDO EN CIERRE] `identity_wall_seconds` podía subcontar trabajo identity-aware

El tiempo total de diarización ya incluía todas las operaciones, pero la métrica específica `identity_wall_seconds` sumaba la etapa final y el precheck inicial, omitiendo evaluaciones ligeras adicionales usadas al comparar candidatos identity-aware. Se añadió `vtt_diarization_v52_metrics.py`, que acumula todas las invocaciones `_light_identity` y expone:

- `final_stage_wall_seconds`;
- `light_identity_wall_seconds`;
- `total_wall_seconds`.

`identity_wall_seconds` queda igualado al total acumulado. Se añadió regresión que simula dos evaluaciones ligeras y comprueba que no se pierden ni duplican tiempos. No cambia la lógica acústica ni la selección de hablantes.

## 4. Verificaciones reproducibles V5.2

### Smoke acústico

Workflow temporal ejecutado dos veces y eliminado después.

- 2 hablantes → 2 detectados.
- 4 hablantes → 4 detectados.
- una pasada en ambos.
- reutilización de modelos, motor y extractor en el segundo trabajo.
- PCM de identidad reutilizado desde diarización.

Esto es un smoke de conteo/reutilización, no DER/JER.

### Benchmark ASR público

Sobre `jfk.flac` de OpenAI en el runner utilizado:

```text
medium / Preciso      ~5.9 s · ~1.87x
medium / Equilibrado  ~4.6 s · ~2.38x
small  / Preciso      ~3.2 s · ~3.47x
small  / Equilibrado  ~1.5 s · ~7.45x
```

Las cuatro salidas tuvieron similitud textual 1.000 frente a medium/Preciso en esa muestra. No extrapolar a español, otro hardware o al audio real del usuario.

### Desktop checks final

`Desktop checks #69`, run `34407637074`, commit `5d6ceece5b24a46cb1c25e269d1a175ddda025e3`: **success**. `py_compile` y `pytest` terminaron correctamente en Ubuntu, Windows y macOS. Esta ejecución incluye `vtt_diarization_v52_metrics.py` y las regresiones de contabilidad completa de identidad.

### Android final

`Android APK #26`, commit `1f6bf9ea8cbca01cc19264dabd2718e49f85e311`: **success**.

- build debug: success;
- upload del APK: success;
- release rodante: success;
- job release firmado: sin keystore, pasos de firma omitidos explícitamente.

### PyInstaller V5.2 final

`Desktop executables #8`, run `34407796151`, commit de build `5b2703d44f5196aa70769ae54ae6d945dab90d26`: **success** en Windows, Ubuntu y macOS.

Artefactos:

```text
Windows  126.869.051 bytes  sha256:6d949ec154ed831631f99bf865c75a7261ade18ba546dfccd78ad828d6be8438
Ubuntu   186.195.924 bytes  sha256:3c38cc9f16e67fc919d41bc0d560b8d310e662528a65336c28d4175843594e9d
macOS    198.803.581 bytes  sha256:9f495afc5e0f11cac65fb188f5aa5764ceaa15324fe53ea6ab375b303f4f2890
```

Expiran el 8 de diciembre de 2026.

### Limpieza

- workflow temporal acústico/hash/benchmark: eliminado;
- trigger temporal de `desktop-build.yml`: retirado;
- `desktop-build.yml` restaurado exactamente al blob permanente `93d5121a6ec87c3fa05a9fff238749a567e479dc`, con `workflow_dispatch` como único disparador;
- el árbol final conserva únicamente `android-build.yml`, `desktop-build.yml` y `desktop-check.yml` dentro de `.github/workflows`;
- no quedan archivos temporales de validación en `.github/workflows`.

## 5. Límites que permanecen

No quedan como deuda de código los antiguos pendientes de bloques Android, pins de Actions, hashes esperados Android, fuga del Handle JNI ni contabilidad incompleta de tiempos de identidad.

Requieren prueba externa/manual:

- calidad acústica exacta en el audio real del usuario;
- efecto real del precheck V5.2 sobre tiempo/calidad en audios con sobredetección;
- DER/JER con corpus temporalmente anotado;
- micrófono/loopback en hardware real;
- apertura/uso de ejecutables PyInstaller en equipos reales;
- Android físico: empalmes largos, RAM, batería, temperatura y actualización firmada;
- GPU CUDA en hardware compatible.

## 6. Resultado de cierre

La rama queda **cerrada para código, pruebas automatizadas, smoke reproducible, hardening de modelos/workflows, documentación y empaquetado V5.2**. Lo pendiente es validación acústica o de hardware real y no debe declararse resuelto sin esa evidencia.
