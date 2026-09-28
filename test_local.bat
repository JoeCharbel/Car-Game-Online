@echo off
echo Starting Car Game Online - Local Test (2 instances)
echo.
echo Instance 1 (Host) starting...
start "Car Game - Host" python online_game.py
timeout /t 2 /nobreak >nul
echo Instance 2 (Client) starting...
start "Car Game - Client" python online_game.py
echo.
echo Both instances launched!
echo  - Instance 1: Click "Host Game"
echo  - Instance 2: Enter 127.0.0.1 and click "Join Game"
