# AGENTS.md — Reglas del repositorio VtT

Contrato para cualquier persona o agente que modifique este repositorio.

## 1. Producto y plataformas

VtT es un transcriptor local y privado con dos aplicaciones relacionadas pero no equivalentes:

- `desktop/`: Python/Tkinter, faster-whisper y diarización opcional sherpa-onnx.
- `android/`: Kotlin + whisper.cpp/JNI. Android no incorpora actualmente la diarización V5.1 del escritorio.

## 2. Reglas inquebrantables

1. **Offline-first y privado.** El audio del usuario no se envía a servicios de transcripción. Red solo para instalación/actualización de dependencias, descarga inicial de modelos, descarga explícita de YouTube y CI/build.
2. **Sin telemetría.** No añadir analytics, tracking ni llamadas de red no necesarias para las funciones anteriores.
3. **Instalación simple.** Escritorio: Python 3.9+ y `run.bat`/`run.sh`/`python run.py`. Android: APK.
4. **Sin privilegios de administrador en el flujo normal de Windows.** Si una solución requiere un paquete de sistema en Linux o un dispositivo virtual en macOS, debe advertirse y documentarse.
5. **Nunca perder trabajo.** Grabaciones/transcripciones deben ir a destinos persistentes; las exportaciones no deben sobrescribir silenciosamente archivos del usuario.
6. **No confundir estimación con certeza.** El número Auto de hablantes y la confianza V5.1 son estimaciones acústicas; solo existe ground truth cuando se aporta externamente.
7. **Idioma del producto:** UI, mensajes y documentación en español. Mantener identificadores existentes cuando renombrarlos no aporte valor.
8. **Compatibilidad:** escritorio Python ≥3.9; Android minSdk 24 y `arm64-v8a` salvo decisión explícita.
9. **No versionar** `.venv`, modelos descargados, grabaciones, transcripciones de usuario, builds, APK o temporales.
10. **Verificar APIs externas.** Antes de usar una API de una dependencia, comprobar la firma de la versión realmente utilizada.
11. **No inventar hashes.** Si una fuente no publica un digest esperado confiable, documentar la limitación y usar las comprobaciones disponibles sin presentarlas como autenticación de origen.
12. **Cambios con verificación.** Antes de modificar, definir cómo se comprobará; después ejecutar esa comprobación antes de declarar el cambio correcto.

## 3. Arquitectura de escritorio

El escritorio ya no es monolítico. `transcriptor_whisper.py` conserva la base histórica de UI, grabación, YouTube y utilidades; las funciones nuevas se implementan en módulos separados.

Entry point final: `desktop/vtt_main.py`.

Capas principales:

- `vtt_core.py`: estructuras, bloques, métricas y exportación base.
- `vtt_alignment.py`: alineación palabra↔hablante.
- `vtt_diarization_v5.py`: motor/worker persistente, Auto e instrumentación.
- `vtt_diarization_v51.py`: verificación acústica de identidad.
- `vtt_identity.py`: prototipos, consistencia y escaneo local.
- `vtt_pipeline_v51.py`: pipeline final.
- `vtt_reporting_v51.py`: JSON schema v6 y DOCX diagnóstico.
- `vtt_ui_v51.py`: indicaciones de costo/recomendación de diarización.

No vuelva a concentrar lógica nueva en `transcriptor_whisper.py` si puede vivir en una capa específica.

### Hilos y Tk

Los hilos de trabajo no deben modificar widgets directamente. La comunicación con Tk se hace mediante colas y `root.after`/mecanismos existentes. Mantener el worker de diarización fuera del hilo de UI.

### Diarización

- `Equilibrada` es el perfil recomendado.
- `Precisa` tiene alto costo CPU.
- Una intervención breve no se fusiona solo por duración.
- Turnos largos no deben formar prototipos de identidad si pueden contener varias voces.
- En modo manual de número de hablantes, no crear identidades adicionales automáticamente sin una decisión explícita de diseño.

## 4. Android

El trabajo de transcripción vive en `TranscribeViewModel` (`viewModelScope`). `Transcriber` sincroniza carga/transcripción/liberación del contexto nativo. `requestAbort()` es la vía no bloqueante de cancelación.

El audio largo sigue siendo una deuda conocida: `AudioDecoder` mantiene el PCM completo en memoria. No introducir un procesamiento por bloques sin resolver timestamps, solape, deduplicación y cancelación y sin probarlo en un dispositivo físico.

Los modelos descargados usan sidecars de tamaño/hash para integridad local. Eso no sustituye un hash esperado de origen.

## 5. Verificación obligatoria

Si se toca `desktop/*.py`:

```text
python -m py_compile <módulos afectados>
python -m pytest tests -q
```

La verificación final oficial es `Desktop checks` en Windows/macOS/Ubuntu.

Si se toca empaquetado o imports del entrypoint, ejecutar también `Desktop executables` con PyInstaller en los tres SO.

Si se toca `android/`, no cerrar la tarea hasta que `Android APK` compile en verde. Las pruebas de hardware real siguen siendo manuales.

Si se toca diarización/identidad, añadir o actualizar pruebas de lógica pura y, cuando sea posible, ejecutar smoke acústico con audios de ground truth conocido.

## 6. Documentación

Un documento no puede describir como actual una arquitectura antigua. Actualizar el README relevante en el mismo ciclo cuando cambien:

- mínimos de Python/Android;
- entrypoint;
- formato JSON;
- perfiles;
- dependencias;
- limitaciones;
- comportamiento de Auto/identidad.

## 7. Qué no hacer

- No reescribir la aplicación en Electron/Qt/web sin una decisión de producto.
- No usar `sounddevice.WasapiSettings(loopback=True)`; el loopback de Windows se implementa con `soundcard`.
- No afirmar que Android tiene diarización si no existe en el código Android.
- No presentar la confianza V5.1 como identificación biométrica.
- No hacer reintentos indefinidos. Si el mismo problema persiste tras 5–10 intentos con cambios razonables, documentar causa, evidencia y limitación, y continuar con el siguiente problema.
