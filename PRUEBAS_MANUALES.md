# Pruebas manuales obligatorias — VtT

Este archivo registra pruebas que la CI no puede sustituir. Cada ejecución manual debe anotar: fecha, commit/artefacto, equipo, SO, configuración, resultado y evidencia no sensible.

Estados permitidos: `PENDIENTE`, `OK`, `FALLA`, `NO_APLICA`.

## 1. Escritorio — instalación y arranque

### Windows

- [ ] Ejecutar `run.bat` en una ruta con espacios, paréntesis y tildes.
- [ ] Probar Python 3.9+ sin privilegios de administrador.
- [ ] Con `.venv` antigua, modificar/actualizar `requirements.txt` y comprobar que `run.py` detecta el hash distinto e instala dependencias.
- [ ] `python run.py --repair` reconstruye dependencias sin tocar transcripciones del usuario.
- [ ] La ventana principal cabe en la pantalla; puede redimensionarse y el área de texto/registro puede agrandarse o reducirse.

### macOS/Linux

- [ ] Arranque mediante `run.sh`/`python3 run.py`.
- [ ] En Linux, confirmar mensaje claro si faltan Tk/PortAudio.
- [ ] En macOS, confirmar que transcripción de archivo funciona sin BlackHole y que loopback solo se ofrece/documenta cuando existe dispositivo virtual.

## 2. Escritorio — entrada de archivos y salidas

- [ ] Audio MP3/WAV/M4A/OGG/FLAC.
- [ ] Video MP4/WEBM/MKV/MOV con audio.
- [ ] Contenedor soportado sin pista de audio: debe rechazarse antes de transcribir.
- [ ] Archivo dañado + archivo válido en el mismo lote: informar éxito parcial y continuar.
- [ ] Repetir una transcripción existente: crear `nombre (2)` y no sobrescribir el original.
- [ ] Cancelar cuando ya existen segmentos: guardar salida parcial claramente identificada.
- [ ] Descarga YouTube: las salidas finales no deben quedar dentro del temporal que se elimina al cerrar.

## 3. Grabación

### Micrófono

- [ ] Iniciar/detener dos grabaciones dentro del mismo segundo: ambos WAV deben existir y ser distintos.
- [ ] El medidor de nivel se mueve.
- [ ] Desconectar/cambiar el dispositivo durante la grabación: debe aparecer error/aviso, no una UI eternamente en “Grabando”.
- [ ] Detener con disco lento o cola pendiente: el WAV solo se anuncia como listo cuando el writer terminó.

### Audio del sistema

Windows:

- [ ] Seleccionar una entrada de loopback de `soundcard`.
- [ ] Reproducir audio en navegador/app y confirmar que el medidor se mueve.
- [ ] El WAV resultante contiene el audio reproducido y no solo estática/silencio.
- [ ] Deshabilitar o desconectar el dispositivo durante la captura: conservar parcial y mostrar error.

Linux/macOS:

- [ ] Probar monitor PulseAudio/PipeWire si existe.
- [ ] En macOS, probar BlackHole u otro dispositivo virtual cuando corresponda.

## 4. ASR

Para un mismo audio corto, registrar:

- modelo;
- Perfil ASR;
- backend;
- Batch;
- Beam;
- carga de modelo;
- ASR seconds;
- procesamiento total.

- [ ] Rápido.
- [ ] Equilibrado.
- [ ] Preciso.
- [ ] GPU automática en un equipo con CUDA compatible, si existe; confirmar fallback CPU si el backend falla.

No comparar velocidad entre PCs distintos como si fuera efecto exclusivo del perfil.

## 5. Diarización y V5.1

Prueba mínima con un audio de varios hablantes cuyo contenido pueda escucharse manualmente.

Configuración recomendada de referencia:

- ASR: Equilibrado o Preciso según objetivo;
- hablantes: Auto;
- diarización: Equilibrada;
- Word/JSON: activos para diagnóstico.

Registrar:

- estimación Auto y confianza;
- perfil/Window shift;
- pasadas Auto y motivo;
- tiempo de diarización;
- wall pasada 1 y pasada 2;
- worker job/modelos/motor reutilizado;
- segmentos divididos y cambios internos;
- control identidad V5.1;
- embeddings calculados;
- turnos reasignados;
- cambios locales;
- consistencia global y por Persona.

Comprobar manualmente:

- [ ] una misma `Persona N` no representa de forma evidente dos voces diferentes;
- [ ] intervenciones cortas reales no desaparecen solo por su duración;
- [ ] cambios claros de voz dentro de un segmento largo producen cortes razonables;
- [ ] Auto con baja confianza se presenta como estimación, no como certeza;
- [ ] fijar manualmente N mantiene el conteo solicitado y V5.1 no inventa nuevas identidades.

## 6. Reutilización/rendimiento

Sin cerrar VtT:

1. transcribir un archivo con diarización;
2. transcribir otro con el mismo perfil.

- [ ] El segundo trabajo indica reutilización de modelos/motor cuando corresponde.
- [ ] Registrar diferencia de preparación/inicialización.
- [ ] Cambiar el perfil de diarización y comprobar que el motor se reinicializa cuando cambia `window_shift_ratio`.

## 7. Smoke acústico reproducible del proyecto

Estos audios oficiales se usan como smoke automatizado porque tienen número conocido de hablantes:

- `1-two-speakers-en.wav` → 2;
- `0-four-speakers-zh.wav` → 4.

El smoke V5.1 debe verificar:

- [ ] conteo 2/4;
- [ ] `identity_verification.enabled=true`;
- [ ] resultado no vacío;
- [ ] segunda tarea reutiliza el motor compatible;
- [ ] la capa de identidad no destruye el conteo correcto.

Esto **no sustituye** un benchmark de diarización con ground truth temporal completo.

## 8. Android físico ARM64

- [ ] Primera descarga de `tiny/base`; cortar red a mitad y confirmar reanudación.
- [ ] Tras descargar, activar modo avión y transcribir un audio local.
- [ ] Rotar la pantalla durante transcripción: el trabajo continúa.
- [ ] Enviar la app al fondo y volver.
- [ ] Cancelar durante descarga, decodificación y transcripción.
- [ ] Compartir audio desde otra app mediante ACTION_SEND.
- [ ] Abrir audio/video mediante ACTION_VIEW.
- [ ] Editar texto y guardar TXT.
- [ ] Guardar SRT sin edición global; con edición, comprobar advertencia de que SRT conserva segmentos originales.
- [ ] Reiniciar el proceso y comprobar restauración del último documento.
- [ ] Probar audio de 10, 60 y >90 minutos y registrar memoria, tiempo, batería y temperatura.
- [ ] Si un audio largo provoca OOM, debe mostrarse mensaje accionable en vez de un crash sin explicación.

## 9. APK/release

- [ ] APK debug del workflow `Android APK` se instala y abre.
- [ ] Si hay secrets de firma, `assembleRelease` produce APK firmado y `.sha256`.
- [ ] Ejecutar la prueba de actualización descrita en `android/RELEASE_SETUP.md` antes de distribuir un release como actualización de otro.

## 10. Registro de resultados

No marcar este documento globalmente como “ejecutado” por una sola prueba. Añadir debajo una entrada por campaña:

```text
Fecha:
Commit/artefacto:
Equipo/SO:
Pruebas ejecutadas:
Resultado:
Fallos/limitaciones:
Evidencia:
```
