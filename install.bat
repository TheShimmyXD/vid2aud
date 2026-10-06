@echo off
rem Instala vid2aud en Windows: entorno virtual, dependencias y acceso en el menu Inicio.
setlocal
cd /d "%~dp0"

set "PY=python"
where py >nul 2>nul && set "PY=py -3"

%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)" >nul 2>nul
if errorlevel 1 (
    echo vid2aud necesita Python 3.12 o superior.
    echo Descargalo de https://www.python.org/downloads/ y marca "Add python.exe to PATH".
    goto :error
)

%PY% -m venv .venv || goto :error
.venv\Scripts\python -m pip install --upgrade pip || goto :error
.venv\Scripts\python -m pip install -r requirements.txt || goto :error
.venv\Scripts\python main.py --install-launcher || goto :error

echo.
echo Listo. Abre vid2aud desde el menu Inicio o con:
echo   .venv\Scripts\python main.py
pause
exit /b 0

:error
echo.
echo La instalacion no termino. Revisa el mensaje de arriba.
pause
exit /b 1
