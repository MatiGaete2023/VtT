# Pruebas manuales obligatorias

Estado: **PRUEBA_ESCRITA_NO_EJECUTADA**. Completar para cada versión con fecha,
commit/APK, equipo, sistema operativo, resultado y evidencia no sensible.

## Windows

1. Instalar o copiar VtT en una ruta con espacios, paréntesis y tildes.
2. Ejecutar python run.py --update; comprobar que abre la interfaz.
3. Grabar dos audios iniciados dentro del mismo segundo, detenerlos y
   comprobar que ambos WAV se reproducen completos.
4. Probar micrófono, archivo local, enlace YouTube válido/inválido y falta
   simulada de yt-dlp; el botón debe poder reintentarse.
5. Probar lote con un archivo dañado y otro válido; informar éxito parcial.
6. Cancelar y cerrar durante transcripción; conservar solo el avance
   confirmado y no afirmar que el parcial es completo.

## Android físico ARM64

1. Preparar un modelo conectado a internet, activar modo avión y transcribir
   un audio local: no debe requerir red para inferir.
2. Cancelar durante comprobación, decodificación, carga e inferencia.
3. Probar audio de 10, 60 y más minutos; registrar memoria, tiempo, batería y
   temperatura.
4. Corregir texto, guardar TXT y pedir SRT: el SRT debe advertir que usa
   segmentos originales si existe edición global.
5. Rotar, enviar la aplicación al fondo, revocar URI y reiniciar el proceso:
   comprobar recuperación o mensaje claro.
6. Cuando exista release firmada, ejecutar la prueba de actualización indicada
   en android/RELEASE_SETUP.md.
