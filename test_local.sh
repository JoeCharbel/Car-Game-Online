#!/usr/bin/env bash
# macOS / Linux equivalent of test_local.bat
# Launches two instances of the game so you can test multiplayer on one machine.
#   Instance 1: click "Host Game"
#   Instance 2: enter 127.0.0.1 and click "Join Game"
cd "$(dirname "$0")" || exit 1

echo "Starting Car Game Online - Local Test (2 instances)"
python3 online_game.py &
sleep 2
python3 online_game.py &

echo
echo "Both instances launched!"
echo " - Instance 1: Click \"Host Game\""
echo " - Instance 2: Enter 127.0.0.1 and click \"Join Game\""
wait
