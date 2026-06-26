cmake_minimum_required(VERSION 3.22)
project(whisper_jni CXX C)

set(CMAKE_CXX_STANDARD 17)

include(FetchContent)

# Descarga whisper.cpp en tiempo de compilacion (fijado a una version estable).
# Asi no hay que versionar el codigo C++ ni usar submodulos.
FetchContent_Declare(
    whisper
    GIT_REPOSITORY https://github.com/ggerganov/whisper.cpp.git
    GIT_TAG        v1.7.4
    GIT_SHALLOW    TRUE
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
