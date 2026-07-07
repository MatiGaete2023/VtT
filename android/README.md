# Transcriptor VtT — versión Android (APK nativo, 100 % offline)

App Android que transcribe audio a texto **en el propio teléfono**, sin enviar nada
a internet. Usa [whisper.cpp](https://github.com/ggerganov/whisper.cpp) compilado de
forma nativa. El modelo de voz se descarga **una sola vez** la primera vez que lo usas
y luego funciona sin conexión.

## Instalar sin Android Studio (recomendado)

No necesitas instalar nada de desarrollo. El APK lo construye GitHub Actions:

1. En GitHub, abre la pestaña **Actions** → flujo **"Android APK"**.
2. Entra a la ejecución más reciente que esté en verde y descarga el artefacto
   **`TranscriptorVtT-debug-apk`** (es un `.zip` que contiene el `.apk`).
   - También se adjunta a la *Release* `android-latest` cuando el flujo corre en la rama.
3. Pasa el `.apk` a tu teléfono (cable, Drive, WhatsApp Web, etc.).
4. Ábrelo en el teléfono y acepta **"Instalar apps de orígenes desconocidos"** cuando
   te lo pida (es normal para apps fuera de Play Store).

## Cómo se usa

1. Elige **Modelo** (`tiny` rápido · `base` equilibrado · `small` más preciso).
2. Elige **Idioma** (Español, Inglés… o Detección automática).
3. Toca **Seleccionar audio** y escoge un archivo (mp3, m4a, wav, ogg, mp4…), o
   **comparte un audio/video desde otra app** (WhatsApp, Chrome, un gestor de
   archivos…) eligiendo "Transcriptor VtT" en el menú Compartir.
4. Toca **Transcribir**. La barra de progreso muestra el avance real; puedes
   **Cancelar** en cualquier momento.
   - La **primera vez con cada modelo** se descarga el modelo (necesita internet).
   - Después transcribe **offline**.
5. **Copia**, **guarda como .txt** o **comparte** el texto resultante. El `.txt`
   se guarda ajustado a ~100 caracteres por línea, igual que en la versión de PC.

> Sugerencia: en el teléfono, empieza con el modelo `tiny` o `base`. `small` es más
> preciso pero más lento y pesado; conviene en equipos con buena RAM.

> Puedes rotar la pantalla o cambiar de app durante una transcripción larga: el
> trabajo sigue en curso y el resultado te espera al volver.

## Tamaño de los modelos (se bajan una vez)

| Modelo | Tamaño aprox. | Velocidad | Precisión |
|--------|---------------|-----------|-----------|
| tiny   | ~75 MB        | muy rápida | básica    |
| base   | ~142 MB       | rápida     | buena     |
| small  | ~466 MB       | media      | mejor     |

## Compilar localmente (opcional, si tienes Android Studio)

1. Abre la carpeta `android/` en Android Studio (Giraffe o superior, JDK 17).
2. Acepta instalar el **NDK 26.3.11579264** y **CMake 3.22.1** cuando lo pida.
3. `Run` ▶ con el teléfono conectado, o `Build > Build APK(s)`.

La primera compilación descarga whisper.cpp (vía CMake `FetchContent`) y compila la
parte nativa; puede tardar varios minutos.

## Detalles técnicos

- Núcleo nativo: `whisper.cpp` (tag `v1.7.4`), compilado con el NDK para `arm64-v8a`.
- Puente JNI: `app/src/main/cpp/whisper_jni.cpp` ↔ `WhisperBridge.kt`. Reporta
  progreso real (`progress_callback` de whisper.cpp) y admite cancelación
  (`abort_callback`, sondeado durante el cómputo).
- El trabajo de transcripción vive en `TranscribeViewModel` (`viewModelScope`),
  no en la Activity: sobrevive a la rotación de pantalla sin perder el resultado
  ni arriesgar un crash nativo por liberar el modelo mientras se usa.
- Decodificación de audio con `MediaCodec`/`MediaExtractor` → PCM mono 16 kHz.
- Modelos GGML descargados de Hugging Face (`ggerganov/whisper.cpp`).
- Sin permisos de almacenamiento: usa el selector de archivos del sistema (SAF).
  El único permiso es `INTERNET`, solo para bajar el modelo la primera vez.
- Icono propio: micrófono blanco sobre violeta de marca (`#6C4DF2`), adaptativo
  en Android 8+.

> Nota: se compila únicamente para `arm64-v8a` (prácticamente todos los teléfonos
> desde ~2016). Para soportar emuladores x86_64 o equipos muy antiguos, añade esas
> ABI en `app/build.gradle` (`abiFilters`).
