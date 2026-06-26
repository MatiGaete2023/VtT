# Mantener los metodos nativos JNI del puente con whisper.cpp.
-keepclasseswithmembernames class * {
    native <methods>;
}
-keep class cl.vtt.transcriptor.WhisperBridge { *; }
