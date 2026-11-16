@echo off
setlocal
rem Build the folder version of the game: dist\CarGame\CarGame.exe
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
    echo Install it with:  py -3.14 -m pip install pygame pyinstaller
    echo.
    pause
    exit /b 1
)

echo Using: %PYTHON%
echo.

%PYTHON% -m pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    %PYTHON% -m pip install pyinstaller
    if errorlevel 1 goto :failed
)

echo Building CarGame.exe ...
%PYTHON% -m PyInstaller --noconfirm --clean CarGame.spec
if errorlevel 1 goto :failed

echo.
echo Done. Run:  dist\CarGame\CarGame.exe
echo Share the whole dist\CarGame folder - the exe needs the files beside it.
echo.
pause
exit /b 0

:failed
echo.
echo Build failed. See the messages above.
echo.
pause
exit /b 1
