# Contributing

Thanks for your interest in working on Car Game Online!

## Setup

```bash
git clone https://github.com/<your-username>/car-game-online.git
cd car-game-online
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

You can launch the game from any working directory — assets are resolved from the source folder by `paths.py`, not from the current directory.

```bash
python game.py        # mode menu: 1 = single player, 2 = online
```

## Testing multiplayer changes

You don't need a second computer.

- **Windows:** run `test_local.bat` — it opens two online-mode windows.
- **Any OS:** run `python online_game.py` twice, in two terminals (or `python game.py` twice and pick online).

Click **Host Game** in the first, then enter `127.0.0.1` and click **Join Game** in the second. Ready up in both and start the game from the host window.

When you change anything in `network.py` or the message handling in `online_game.py`, test at least:

- Host and one client completing a full round (start → crash → game over → return to lobby)
- A client disconnecting mid-round (close its window)
- The host disconnecting mid-round (clients should return to the menu)
- A third player joining while a round is running (should spectate, then play the next round)
- Traffic staying in sync on both windows for a full round, including the fast bus

If a change affects gameplay, check it in single player too — traffic rules and the bus are shared between the two modes and are meant to behave identically.

## Where things live

| File | What it does |
|---|---|
| `game.py` | `CarGame` launcher: mode menu, owns the window, runs one mode at a time |
| `singleplayer.py` | Single-player mode: endless traffic, score, pause, high-score entry |
| `online_game.py` | `OnlineGame` with one `_update_*` method per screen (menu, lobby, countdown, playing, game over) and `_process_*` methods for networking |
| `network.py` | `GameServer` / `GameClient` and the length-prefixed JSON framing |
| `highscores.py` | `scores.json` load/save, top 10 per mode |
| `paths.py` | `resource_path()` for read-only assets, `writable_path()` for save files; works from source and from a frozen build |
| `CarGame.spec`, `build.bat` | PyInstaller folder build → `dist\CarGame\CarGame.exe` |

If you add a new message type, handle it in `_process_host_messages` and/or `_process_client_messages` and add it to the message table in the README.

## Pull requests

- Keep PRs focused on one change
- Describe how you tested it (single-player, local two-instance test, or over a real network)
- Don't commit `__pycache__/`, `.pyc` files, `build/`, `dist/` or `scores.json` (all in `.gitignore`)

## Ideas for contributions

- Configurable port, and showing the correct IP on multi-adapter machines
- Sound effects and music
- Move image assets into an `assets/` folder
- Host migration or reconnect after the host drops
- An icon for the packaged exe (`CarGame.spec`)
