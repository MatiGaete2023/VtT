# Publicación release estable

Estado: **[CONFLICTO_ABIERTO]** hasta que el propietario configure una clave
de producción. No se debe reutilizar, subir ni enviar por correo una clave privada.

## Una sola vez

1. Decide el paquete de producción: actualmente es cl.vtt.transcriptor.
   El APK debug usa cl.vtt.transcriptor.debug y no se actualiza sobre él.
2. Crea o recupera la clave de producción bajo control del propietario.
   Conserva una copia cifrada fuera del repositorio y registra la huella del certificado.
3. Configura en GitHub Actions los secretos ANDROID_KEYSTORE_B64,
   ANDROID_KEYSTORE_PASSWORD, ANDROID_KEY_ALIAS y ANDROID_KEY_PASSWORD.
4. Ejecuta el workflow Android APK. Si los secretos están presentes, genera un
   APK release con versionCode creciente, verifica la firma con apksigner
   y publica el SHA-256 como artefacto junto al APK.

## Antes de distribuir

1. Instala una release en un teléfono de prueba.
2. Genera y guarda un proyecto.
3. Instala una segunda release firmada con el mismo certificado y número de versión mayor.
4. Comprueba que la actualización no pide desinstalar y que el proyecto sigue disponible.

Las instalaciones debug previas se mantienen como otra aplicación. Exporta
sus transcripciones antes de eliminarla: Android no entrega automáticamente
su almacenamiento privado a una aplicación release distinta.
