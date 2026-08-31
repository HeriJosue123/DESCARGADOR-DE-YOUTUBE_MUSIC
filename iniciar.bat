@echo off
title Music Downloader Local
color 0b
echo ========================================================
echo     Music Downloader Local - Setup ^& Run Script
echo ========================================================
echo.

:: Verificar si python está instalado
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python no esta instalado o no esta en el PATH de Windows.
    echo Por favor instala Python 3 desde la Microsoft Store o python.org
    pause
    exit /b
)

:: Crear entorno virtual si no existe
if not exist "venv\" (
    echo [INFO] Creando entorno virtual local...
    python -m venv venv
)

:: Activar entorno virtual
call venv\Scripts\activate.bat

:: Instalar dependencias
echo [INFO] Verificando dependencias necesarias...
python -m pip install --upgrade pip >nul 2>&1
pip install -r requirements.txt >nul 2>&1

echo.
echo ========================================================
echo [EXITO] SERVIDOR LISTO Y PROTEGIDO
echo.
echo USO PERSONAL:
echo Entra a: http://localhost:5000
echo.
echo COMPARTIR CON AMIGOS:
echo 1. Deja esta ventana negra abierta.
echo 2. Abre una NUEVA ventana de terminal.
echo 3. Ejecuta el comando: ngrok http 5000
echo 4. Copia el link que dice "Forwarding (ej. https://xxxx.ngrok.app)"
echo 5. Pasale ese link a tus amigos.
echo.
echo IMPORTANTE: El PIN de acceso configurado es: 2026
echo (Puedes cambiarlo abriendo app.py en un bloc de notas)
echo ========================================================
echo.
python app.py
pause
