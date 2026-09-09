# Transcriptor VtT — versión Android

App Android ARM64 que transcribe audio a texto **en el propio teléfono** con `whisper.cpp`. El audio no se envía a una API de transcripción. El modelo se descarga una vez y luego puede utilizarse sin conexión.

Android sigue siendo una aplicación distinta de VtT escritorio: **no incorpora diarización de hablantes**.

## Instalar sin Android Studio

1. En GitHub abre **Actions → Android APK**.
2. Entra a una ejecución verde y descarga `TranscriptorVtT-debug-apk`.
3. Extrae `TranscriptorVtT.apk`, pásalo al teléfono y ábrelo.
4. Android puede pedir autorización para instalar aplicaciones desde esa fuente porque el APK no proviene de Play Store.

El workflow también mantiene una release rodante `android-latest`. Un release firmado con una clave propia solo se genera si el repositorio tiene configurados los secretos de firma.

## Uso

1. Elige modelo: `tiny`, `base` o `small`.
2. Elige idioma o detección automática.
3. Selecciona un audio/video o compártelo desde otra app mediante el menú Compartir.
4. Pulsa **Transcribir**. Se muestra progreso y puedes cancelar.
5. Copia, edita, guarda TXT/SRT o comparte el resultado.

El último documento se conserva en el almacenamiento interno de la app, con el texto reconocido y las correcciones humanas separados. El respaldo automático de Android está desactivado.

## Modelos y seguridad de la primera descarga

Fuente: `ggerganov/whisper.cpp` en Hugging Face.

| Modelo | Tamaño aprox. | Uso orientativo |
|---|---:|---|
| tiny | ~75 MB | máxima velocidad |
| base | ~142 MB | equilibrio |
| small | ~466 MB | mayor precisión/costo |

`ModelManager` descarga a `.part`, reanuda mediante `Range` cuando corresponde y valida `Content-Range` antes de anexar. Desde septiembre de 2026, el archivo completo debe coincidir además con el SHA-256 esperado antes de ser promovido a modelo válido:

```text
tiny  be07e048e1e599ad46341c8d2a135645097a538221678b7acdd1b1919c6e1b21
base  60ed5bc3dd14eea856493d334349b405782ddcaf0028d4b5df4088345fba2efe
small 1be3a9b2063867b937e64e2ec7483364a79917e157fa98c5d94b5c1fffea987b
```

Los sidecars `.size` y `.sha256` se conservan como caché/integridad local, pero ya no son la única confianza de la primera descarga. Un modelo antiguo que no coincide con el catálogo se descarta y se descarga nuevamente.

## Audios largos: procesamiento acotado por bloques

Para archivos de más de **5 minutos**, la app evita construir el PCM completo de varias horas en memoria.

Flujo actual:

- ventanas de 90 segundos;
- 2 segundos de solapamiento;
- `AudioDecoder.decodeRange()` usa `MediaExtractor.seekTo()` y recorta los buffers según `presentationTimeUs`;
- cada bloque se convierte a PCM mono 16 kHz y se libera antes de continuar;
- timestamps de segmentos y palabras se trasladan a la línea temporal global;
- el solapamiento se deduplica por el punto medio de los segmentos;
- el modelo whisper se reutiliza entre bloques;
- progreso y cancelación se mantienen.

Esto reduce estructuralmente el riesgo de OOM por PCM largo. Sigue siendo necesario validar en teléfonos reales la calidad del empalme, memoria, batería y temperatura para audios extensos.

## Ciclo de vida y JNI

El trabajo vive en `TranscribeViewModel`, no en la Activity, por lo que una rotación de pantalla no cancela por sí sola la transcripción.

`Transcriber` sincroniza carga/transcripción/liberación. La cancelación nativa usa `abort_callback`.

El JNI ya no expone un puntero crudo que deba dejarse filtrado para evitar una carrera. `whisper_jni.cpp` usa:

- identificadores `jlong` opacos;
- registro protegido por mutex;
- `shared_ptr<Handle>` para mantener vivo el handle mientras una llamada concurrente lo usa;
- mutex separado para la vida de `whisper_context`;
- bandera atómica de aborto que no necesita esperar el mutex de transcripción.

`nativeFree` retira el handle del registro, solicita aborto, espera de forma segura el contexto y libera tanto `whisper_context` como el Handle cuando ya no existen referencias concurrentes.

## Compilar localmente

1. Abre `android/` en Android Studio con JDK 17.
2. Instala NDK `26.3.11579264` y CMake `3.22.1`.
3. Ejecuta la aplicación o `assembleDebug`.

whisper.cpp está fijado al commit exacto `8a9ad7844d6e2a10cddf4b92de4089d7ac2b14a9`, correspondiente al tag `v1.7.4` verificado en la auditoría del proyecto. No cambiar ese pin sin volver a compilar la matriz Android.

La ABI actual es únicamente `arm64-v8a`; ampliar ABI requiere validar de nuevo tamaño, rendimiento y CI.

## Firmar un APK de release

El APK debug puede instalarse directamente. Para un release firmado configura los secretos:

- `ANDROID_KEYSTORE_B64`
- `ANDROID_KEYSTORE_PASSWORD`
- `ANDROID_KEY_ALIAS`
- `ANDROID_KEY_PASSWORD`

El job opcional construye el release, verifica la firma con `apksigner`, genera `.sha256` y limpia el material de firma del runner. Sin keystore el job se omite de forma explícita y no convierte el build debug en fallo.

Consulta `RELEASE_SETUP.md` antes de distribuir una actualización firmada.

## Detalles técnicos

- `MediaCodec` / `MediaExtractor` → PCM mono 16 kHz.
- whisper.cpp nativo, ARM64.
- progreso mediante `progress_callback`.
- cancelación mediante `abort_callback`.
- SAF: no requiere permisos generales de almacenamiento.
- `INTERNET` se utiliza para la primera descarga del modelo.
- Actions del workflow se fijan por SHA.

## Verificación pendiente que CI no sustituye

Aunque el APK compila en CI, todavía deben comprobarse en un teléfono físico:

- instalación/apertura del APK actual;
- reanudación real de una descarga interrumpida;
- modo avión después de descargar el modelo;
- rotación/fondo/cancelación;
- ACTION_SEND/ACTION_VIEW;
- audio largo por bloques, especialmente los empalmes de 2 s;
- memoria, batería y temperatura en 10, 60 y >90 minutos;
- flujo de actualización de un APK firmado.

Estas pruebas se registran en `../PRUEBAS_MANUALES.md`.
