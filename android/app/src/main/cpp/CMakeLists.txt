cmake_minimum_required(VERSION 3.22)
project(whisper_jni CXX C)

set(CMAKE_CXX_STANDARD 17)

include(FetchContent)

# whisper.cpp fijado al commit exacto al que resuelve el release v1.7.4.
# Se usa un SHA y no un tag movil para que builds futuros no cambien de codigo
# nativo sin una modificacion explicita de este archivo.
FetchContent_Declare(
    whisper
    GIT_REPOSITORY https://github.com/ggml-org/whisper.cpp.git
    GIT_TAG        8a9ad7844d6e2a10cddf4b92de4089d7ac2b14a9
    GIT_SHALLOW    FALSE
)

# Opciones para una compilacion Android limpia y minima.
set(WHISPER_BUILD_TESTS    OFF CACHE BOOL "" FORCE)
set(WHISPER_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
set(WHISPER_BUILD_SERVER   OFF CACHE BOOL "" FORCE)
set(GGML_OPENMP            OFF CACHE BOOL "" FORCE)
set(GGML_NATIVE            OFF CACHE BOOL "" FORCE)
set(BUILD_SHARED_LIBS      OFF CACHE BOOL "" FORCE)

FetchContent_MakeAvailable(whisper)

# Nuestra libreria puente JNI.
add_library(whisper_jni SHARED whisper_jni.cpp)

find_library(log-lib log)

target_link_libraries(whisper_jni
    whisper
    ${log-lib}
    android
)
