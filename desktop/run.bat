@echo off
REM Lanzador para Windows. Doble clic aqui para abrir el Transcriptor Whisper.
REM Solo necesita tener Python instalado (https://www.python.org/downloads/).
cd /d "%~dp0"
where py >nul 2>nul
if %ERRORLEVEL%==0 (
    py run.py %*
) else (
    python run.py %*
)
if %ERRORLEVEL% neq 0 (
    echo.
    echo Ocurrio un problema. Asegurate de tener Python instalado.
    echo Descarga: https://www.python.org/downloads/  (marca "Add Python to PATH")
    pause
)
