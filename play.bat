@echo off
setlocal
rem Always run from the game folder, wherever this .bat is launched from.
cd /d "%~dp0"

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

%PYTHON% game.py
