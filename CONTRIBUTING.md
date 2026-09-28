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

Run everything **from the repository root**, because assets are loaded with relative paths.

## Testing multiplayer changes

You don't need a second computer:

- Windows: run `test_local.bat`
- macOS / Linux: run `./test_local.sh`

This opens two game windows. Click **Host Game** in the first, then enter `127.0.0.1` and click **Join Game** in the second. Ready up in both and start the game from the host window.

When you change anything in `network.py` or the message handling in `online_game.py`, test at least:

- Host and one client completing a full round (start → crash → game over → return to lobby)
- A client disconnecting mid-round (close its window)
- The host disconnecting mid-round (clients should return to the menu)

## Where things live

| File | What it does |
|---|---|
| `main_game.py` | Single-player game, one self-contained script |
| `online_game.py` | `OnlineGame` class with one `_update_*` method per screen (menu, lobby, countdown, playing, game over) and `_process_*_messages` for networking |
| `network.py` | `GameServer` / `GameClient` and the length-prefixed JSON framing |

If you add a new message type, handle it in `_process_host_messages` and/or `_process_client_messages` and add it to the message table in the README.

## Pull requests

- Keep PRs focused on one change
- Describe how you tested it (single-player, local two-instance test, or over a real network)
- Don't commit `__pycache__/` or `.pyc` files (they're in `.gitignore`)

## Ideas for contributions

- Fix the bus sprite glitch (see *Known issues* in the README)
- Persist the single-player high score
- Handle players joining mid-round
- Configurable port / host IP shown correctly on multi-adapter machines
- Sound effects and music
- Move image assets into an `assets/` folder
