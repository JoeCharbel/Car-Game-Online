@echo off
setlocal
rem Always run from the game folder, wherever this .bat is launched from.
cd /d "%~dp0"

echo Starting Car Game Online - Local Test (2 instances)
echo.

rem Find a Python that actually has pygame installed.
set "PYTHON="
python -c "import pygame" >nul 2>&1
if not errorlevel 1 set "PYTHON=python"

if not defined PYTHON (
    py -3.14 -c "import pygame" >nul 2>&1
    if not errorlevel 1 set "PYTHON=py -3.14"
)

if not defined PYTHON (
    py -3.13 -c "import pygame" >nul 2>&1
    if not errorlevel 1 set "PYTHON=py -3.13"
)

if not defined PYTHON (
    echo ERROR: Could not find a Python installation with pygame.
    echo.
    echo Install it with:  py -3.14 -m pip install pygame
    echo.
    pause
    exit /b 1
)

echo Using: %PYTHON%
echo.

echo Instance 1 (Host) starting...
start "Car Game - Host" %PYTHON% online_game.py
timeout /t 2 /nobreak >nul
echo Instance 2 (Client) starting...
start "Car Game - Client" %PYTHON% online_game.py
echo.
echo Both instances launched!
echo  - Instance 1: Click "Host Game"
echo  - Instance 2: Enter 127.0.0.1 and click "Join Game"
