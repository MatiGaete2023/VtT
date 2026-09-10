# AUDITORÍA DEL REPOSITORIO — VtT V5.2

**Actualizada:** 9 de septiembre de 2026  
**Rama:** `claude/voice-transcriber-multiplatform-6xifq1`  
**Estado:** **CIERRE DE CÓDIGO, DOCUMENTACIÓN, CI Y EMPAQUETADO VERIFICADO**

Esta auditoría registra el estado V5.2-performance y distingue lo comprobado por código/CI de lo que todavía necesita audio o hardware real.

## 1. Estado ejecutivo

### Escritorio

Estado: **V5.2 implementado, probado y empaquetado**.

- Python 3.9+; entrypoint `desktop/vtt_main.py`.
- ASR: faster-whisper/CTranslate2.
- Diarización: sherpa-onnx.
- Modos globales Rápido/Equilibrado/Preciso/Personalizado.
- Auto estructural + precheck acústico acotado + selección identity-aware.
- Reutilización de modelos, motor, PCM y embeddings.
- Identidad rival-aware y sonda barata antes del escaneo detallado de turnos largos.
- Alineación palabra↔hablante con división interna de segmentos.
- Conteos separados de sherpa / identidad / texto.
- Métricas de identidad separadas en etapa final, evaluaciones ligeras y total acumulado.
- JSON maestro schema v7.
- DOCX V5.2 con rótulos y métricas coherentes con la versión efectiva.
- Modelos sherpa protegidos por hashes auditados fijados en código.
- `Desktop checks #73`: verde en Windows/macOS/Ubuntu.
- `Desktop executables #9`: verde en Windows/macOS/Ubuntu.

### Android

Estado: **ASR local funcional y build verde; sin diarización del escritorio**.

- Kotlin + whisper.cpp/JNI, ARM64, minSdk 24.
- Progreso/cancelación nativa y trabajo en `TranscribeViewModel`.
- Modelos tiny/base/small con SHA-256 esperado antes de aceptar la primera descarga.
- Audios >5 min por bloques de 90 s + 2 s de solapamiento.
- JNI con handles opacos/shared_ptr; eliminada la fuga deliberada anterior.
- whisper.cpp fijado al commit `8a9ad7844d6e2a10cddf4b92de4089d7ac2b14a9`.
- `Android APK #28`: build debug, artefacto y release rodante verdes; release firmado omitido por ausencia de keystore, según diseño.

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

### V52-07 [CORREGIDO] Migración de perfiles podía sobrescribir preferencias V5.1

La migración reconoce un preset solo si los tres controles restaurados coinciden exactamente; cualquier combinación propia queda en Personalizado. Existe prueba de regresión.

### V52-08 [CORREGIDO] Integridad de modelos sherpa dependía de TOFU

Los assets históricos de k2-fsa muestran `digest=null`. Dos descargas independientes desde los assets oficiales reprodujeron los mismos hashes y se auditó además el ONNX extraído:

```text
segmentación archive  24615ee884c897d9d2ba09bb4d30da6bb1b15e685065962db5b02e76e4996488
segmentación model    220ad67ca923bef2fa91f2390c786097bf305bceb5e261d4af67b38e938e1079
embedding 3D-Speaker  1a331345f04805badbb495c775a6ddffcdd1a732567d5ec8b3d5749e3c7a5e4b
```

VtT valida tamaño + hash antes de promover la descarga y valida el ONNX extraído. Son pins auditados por VtT, no digests publicados por upstream.

### V52-09 [CORREGIDO] GitHub Actions antiguas/runtime Node 20

Los workflows relevantes usan revisiones actuales fijadas por SHA. Checkout/setup-python/upload-artifact usan runtime moderno; Android conserva setup-java/setup-android/Gradle/release igualmente fijados por SHA.

### V52-10 [CORREGIDO] Android: primera descarga GGML sin catálogo

`ModelManager` contiene SHA-256 esperados para tiny/base/small y valida antes de promover el archivo.

### V52-11 [CORREGIDO] Android: PCM completo de audios largos

Para >5 min se usa `decodeRange()` y ventanas de 90 s con 2 s de solapamiento. La CI confirma compilación; empalmes/consumo real siguen siendo pruebas físicas.

### V52-12 [CORREGIDO] Handle JNI deliberadamente filtrado

El JNI usa identificadores opacos y registro `shared_ptr`; `nativeFree` puede retirar/liberar el Handle sin reintroducir use-after-free.

### V52-13 [CORREGIDO] `identity_wall_seconds` podía subcontar trabajo identity-aware

`vtt_diarization_v52_metrics.py` acumula todas las evaluaciones ligeras `_light_identity` y separa:

- `final_stage_wall_seconds`;
- `light_identity_wall_seconds`;
- `total_wall_seconds`.

`identity_wall_seconds` queda igualado al total acumulado. La regresión simula múltiples evaluaciones y comprueba que no se pierden ni duplican tiempos. No cambia la lógica acústica.

### V52-14 [CORREGIDO EN REVISIÓN GENERAL] El Word V5.2 conservaba un rótulo V5.1

El writer V5.2 hereda partes de `vtt_reporting_v51.py`; por ello una transcripción nueva podía mostrar `Control identidad V5.1` aunque el motor efectivo fuera V5.2. Además, el desglose final/ligero/total estaba disponible en metadatos, pero no era explícito en Word.

`vtt_reporting_v52.py` corrige ahora el rótulo a `Control identidad V5.2` y expone `Identidad total (wall)`, `Identidad etapa final (wall)` e `Identidad ligera (wall)`. Se añadió regresión que crea un DOCX y comprueba tanto la ausencia del rótulo V5.1 como los tres valores. No se modifica diarización ni ASR.

### V52-15 [CORREGIDO EN REVISIÓN GENERAL] Cambios Markdown disparaban CI pesada

Los filtros anteriores `desktop/**` y `android/**` hacían que editar únicamente README/documentación dentro de esas carpetas ejecutara las matrices completas. Los workflows excluyen ahora `desktop/**/*.md` y `android/**/*.md`, manteniendo el archivo del workflow como trigger para validar cualquier modificación de CI. Esto reduce trabajo innecesario sin omitir cambios ejecutables.

### V52-16 [ACLARADO] Firma Android tratada como conflicto técnico

`android/RELEASE_SETUP.md` marcaba la ausencia de keystore de producción como `[CONFLICTO_ABIERTO]`. Se reclasificó como **PENDIENTE EXTERNO**: el código y workflow existen; falta una credencial que debe proporcionar/configurar el propietario. No se versiona ni se comparte la clave privada.

## 4. Verificaciones reproducibles V5.2

### Smoke acústico

Workflow temporal ejecutado y eliminado después.

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

`Desktop checks #73`, run `34424880813`, commit `7905071096f0bb0478aa07d6b419546a57cb11b7`: **success**. Windows, Ubuntu y macOS pasaron `py_compile` y `pytest`. Esta ejecución incluye la corrección del DOCX V5.2, su regresión y la nueva configuración de filtro documental.

### Android final

`Android APK #28`, run `34424903439`, commit `5f51ae8c197cbd7ec8a72eb8e9c93e1532b2713a`: **success**.

- build debug: success;
- upload del APK: success;
- release rodante: success;
- job release firmado: detección de ausencia de keystore correcta; pasos de firma omitidos según diseño.

Esta ejecución valida además el workflow con el nuevo filtro de documentación; no introduce un cambio funcional Android posterior al build funcional ya auditado.

### PyInstaller V5.2 final tras revisión general

`Desktop executables #9`, run `34425016894`, commit de build `2156cae37ca2ecbaec5c57081d6f6c3409086e10`: **success** en Windows, Ubuntu y macOS.

Artefactos:

```text
Windows  126.869.660 bytes  sha256:da874a760725d77526a8358dd44751988d0c79c4d04f72576871d3d66a74d8e5
Ubuntu   186.194.313 bytes  sha256:577d937bbe8ec7205bfadab540f16d1f4b52d7bd0e066df16c5198ee1e631121
macOS    198.803.059 bytes  sha256:6f2f2f6b9bff8eb34d68ee8cd4446c1c420deef796f3340df4ef71df250323bd
```

Expiran el 9 de diciembre de 2026.

### Limpieza

- workflow temporal acústico/hash/benchmark: eliminado;
- trigger temporal de `desktop-build.yml`: retirado después del build #9;
- `desktop-build.yml` restaurado al blob permanente `93d5121a6ec87c3fa05a9fff238749a567e479dc`, con `workflow_dispatch` como único disparador;
- el árbol permanente debe conservar únicamente `android-build.yml`, `desktop-build.yml` y `desktop-check.yml` dentro de `.github/workflows`.

## 5. Documentación revisada

Se revisaron README raíz, README de escritorio, README Android, `MODEL_CATALOG.md`, `AGENTS.md`, `AUDITORIA.md`, `PLAN_MAESTRO.md`, `PRUEBAS_MANUALES.md` y `android/RELEASE_SETUP.md`.

Actualizaciones principales:

- mapa documental y estructura V5.2 explícitos;
- cadena V4/V5/V5.1 documentada como herencia/compatibilidad, no como múltiples entrypoints;
- `vtt_diarization_v52_metrics.py` y servicio final incorporados al mapa técnico;
- reglas para evitar rótulos de versión obsoletos en reportes;
- distinción entre CI automatizada y validación acústica/hardware;
- firma Android como dependencia externa y no error del producto.

`MODEL_CATALOG.md` y `android/README.md` ya eran coherentes con los hashes, bloques Android y limitaciones actuales; no se cambian solo por incrementar una fecha.

## 6. Límites que permanecen

No quedan como deuda de código los antiguos pendientes de bloques Android, pins de Actions, hashes esperados Android, fuga del Handle JNI, contabilidad incompleta de tiempos de identidad ni rótulos V5.1 en nuevos DOCX V5.2.

Requieren prueba externa/manual:

- calidad acústica exacta en el audio real del usuario;
- efecto real del precheck V5.2 sobre tiempo/calidad en audios con sobredetección;
- DER/JER con corpus temporalmente anotado;
- micrófono/loopback en hardware real;
- apertura/uso de ejecutables PyInstaller en equipos reales;
- Android físico: empalmes largos, RAM, batería, temperatura y actualización firmada;
- GPU CUDA en hardware compatible.

La reproducibilidad Python con lock/hashes transitivos sigue siendo una mejora futura posible: requiere diseñar una matriz de wheels por SO/arquitectura y una política de actualización, no congelar un único runner.

## 7. Resultado de cierre

La rama queda **cerrada para código, pruebas automatizadas, smoke reproducible, hardening de modelos/workflows, documentación y empaquetado V5.2**. Lo pendiente es validación acústica o de hardware real y no debe declararse resuelto sin esa evidencia.
