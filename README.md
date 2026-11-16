# 🚗 Car Game Online

A top-down, pixel-art car dodging game built with [pygame](https://www.pygame.org/), with both a **single-player** mode and an **online multiplayer** mode where friends race through traffic together. One player hosts, everyone else joins by IP address.

## Features

- **Single-player** endless dodging with a saved high score and a pause menu
- **Online multiplayer** over TCP: host/join lobby, ready-up, synchronized traffic and a final scoreboard
- Each player gets a different car colour (8 sprites included)
- Difficulty ramps up as your score grows: faster traffic and more of it
- A rare fast-moving bus in **both** modes — same sprite, same size, same 6% spawn chance, same extra speed, and it stays in its lane
- Crashed? **Spectate** the rest of the round or **leave**
- **Persistent high scores** per mode, saved to `scores.json` next to the game
- One launcher for both modes, plus a Windows `.exe` build that needs no Python

## Requirements

- Python 3.9 or newer (tested on Python 3.14)
- [pygame](https://pypi.org/project/pygame/) 2.0 or newer
- PyInstaller, **only** if you want to build the `.exe` (`build.bat` installs it for you)

## Installation

```bash
git clone https://github.com/<your-username>/car-game-online.git
cd car-game-online

# (optional but recommended) create a virtual environment
python -m venv .venv
# Windows:      .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate

pip install -r requirements.txt
```

> **Very new Python versions:** if `pip install pygame` fails on your Python version (for example a freshly released one), install the community fork instead: `pip install pygame-ce`. It is a drop-in replacement and the game imports it the same way.

## How to run

```bash
python game.py
```

That opens the mode menu: press `1` for **Single Player**, `2` for **Online Multiplayer**. On Windows you can also double-click `play.bat`, which finds a Python that has pygame and launches the same menu.

Shortcuts if you always want the same mode:

```bash
python main_game.py     # straight into single player
python online_game.py   # straight into the online menu
```

Assets are resolved relative to the game files, so the working directory does not matter — launching from anywhere works.

### Play as a packaged Windows build

```bat
build.bat
```

This produces `dist\CarGame\CarGame.exe` plus its `_internal` folder — no Python needed on the target machine. Share the **whole `dist\CarGame` folder** (zipped); the exe will not run without `_internal` beside it.

- Windows SmartScreen warns on first run because the exe is unsigned: **More info → Run anyway**. Only a code-signing certificate removes that.
- Online play still uses TCP port `5555`, exactly as when running from source.
- To rebuild after a code change, run `build.bat` again (or `py -3.14 -m PyInstaller --noconfirm --clean CarGame.spec`).
- `scores.json` is created next to `CarGame.exe`, so scores survive updates as long as you replace only the exe and `_internal`.

## Online multiplayer

1. **Host:** enter a name and click **Host Game**. Your IP address and the port (`5555`) are shown in the lobby.
2. **Everyone else:** enter a name, type the host's IP into **Host IP**, and click **Join Game** (or press Enter in the IP box).
3. Everyone clicks **Ready!**
4. When **2 or more** players are connected and all are ready, the host clicks **Start Game**.
5. After a 3-2-1-GO countdown, dodge the traffic. Last car standing is announced as the winner; the round ends once everyone has crashed and a scoreboard is shown. Click **Return to Lobby** to play again.

Use `Tab` to switch between the name and IP fields. A player who joins while a round is already running watches that round as a spectator and plays from the next one.

### Playing with friends

**Same Wi-Fi / LAN (easiest).** The host shares the IP shown in the lobby and everyone else joins with it. If the host's firewall prompts you on first launch, allow the game through, or open **inbound TCP port 5555**.

**Over the internet.** The game has no matchmaking server, so the host's machine must be reachable. Two options:

- **Virtual LAN (recommended):** everyone installs a tool such as [Tailscale](https://tailscale.com/), [ZeroTier](https://www.zerotier.com/) or Hamachi. The host gives out their address on that virtual network.
- **Port forwarding:** forward TCP port `5555` on your router to the host machine and share your public IP. There is no authentication, so only do this with people you trust.

## Controls

| Key | Action |
|---|---|
| ⬆️ ⬇️ ⬅️ ➡️ Arrow keys | Drive |
| `Esc` | Pause / resume (single-player only) |
| Mouse | Menus and buttons |

## Testing locally (two players on one machine)

Handy when developing or debugging multiplayer without a second computer.

**From source (Windows):** double-click `test_local.bat`, or run it from a terminal in the repo folder. It opens two online-mode windows.

**From source (any OS):** run `python online_game.py` twice. End the second one with `Ctrl+C` in its terminal, or just close the windows.

**From the packaged build:** start `CarGame.exe` twice.

Then in both windows:

- **Instance 1:** click **Host Game**
- **Instance 2:** enter `127.0.0.1` and click **Join Game**
- Click **Ready!** in both, then **Start Game** in the host window

Tip: only the window with keyboard focus receives your key presses, so click on the window you want to drive.

## Project structure

```
car-game-online/
├── game.py            # Launcher: mode menu, runs one mode at a time
├── singleplayer.py    # Single-player mode
├── online_game.py     # Multiplayer: menu, lobby, countdown, play, game over
├── network.py         # TCP server/client and length-prefixed JSON framing
├── highscores.py      # scores.json load/save (top 10 per mode)
├── paths.py           # asset paths for both source runs and frozen builds
├── main_game.py       # Shortcut straight into single player
├── play.bat           # Windows: launch from source
├── test_local.bat     # Windows: two instances for local testing
├── build.bat          # Windows: build dist\CarGame\CarGame.exe
├── CarGame.spec       # PyInstaller definition used by build.bat
├── requirements.txt
├── background.png     # Scrolling road
├── redcar.png         # Player 1 car (also the single-player car)
├── player_*.png       # Seven more player colours
├── enemy.png, enemy2.png   # Traffic cars
├── enemy_bus.png           # Rare fast bus (both modes)
└── scores.json        # Created at runtime, not committed
```

## How multiplayer works

The game uses a simple **host/client (star) topology** over TCP on port `5555` (`PORT` in `online_game.py`).

- The **host** runs a `GameServer` in a background thread *and* plays the game itself. Clients connect with a `GameClient`.
- Messages are **JSON objects with a 4-byte length prefix** (`send_msg` / `recv_msg` in `network.py`).
- The **host decides when traffic spawns** and broadcasts each spawn (`OBSTACLE_SPAWN`). Every client then moves that traffic locally, so everyone sees the same cars. The host also sends an authoritative `WORLD_STATE` snapshot a few times a second to correct drift.
- Each client moves its own car and **reports its position** to the host, which rebroadcasts everyone's state a few times per second.
- Each client **detects its own collisions** and tells the host when it is eliminated. The host announces the winner and ends the round.

| Message | Direction | Purpose |
|---|---|---|
| `JOIN` | client → host | Handshake with the player's name |
| `ASSIGN_ID` | host → client | Player ID assignment |
| `PLAYER_JOINED` | host → all | A player entered the lobby (or joined as a spectator mid-round) |
| `PLAYER_DISCONNECTED` | host → all | A player left or dropped |
| `LOBBY_STATE` | host → all | Player list and ready status |
| `PLAYER_READY` | client → host | Toggle ready |
| `START_GAME` | host → all | Round start, RNG seed, starting positions |
| `OBSTACLE_SPAWN` | host → all | A new traffic vehicle |
| `WORLD_STATE` | host → all | Authoritative traffic positions, lanes and speeds |
| `PLAYER_UPDATE` | client → host | Local car position and score |
| `PLAYER_STATES` | host → all | Everyone's positions, alive status, scores |
| `SPECTATE_JOIN` | host → client | Late joiner watches the running round |
| `PLAYER_ELIMINATED` | client → host | This player crashed |
| `WINNER_ANNOUNCED` | host → all | One player left alive |
| `GAME_OVER` | host → all | Round finished, final scores |
| `RETURN_TO_LOBBY` | host → all | Everyone back to the lobby |

## Known issues and limitations

- **Host leaves = round over for everyone.** There is no host migration or reconnect.
- **The lobby IP can be wrong** on machines with several network adapters (VPNs, virtual machines). It is looked up from the hostname, so if friends can't connect, check your address with `ipconfig` (Windows) or `ip a` / `ifconfig` (macOS/Linux).
- **No cheat protection:** clients report their own positions and collisions and are trusted by the host.
- Only 8 car colours exist, so a 9th player would share a colour.
- No sound effects or music yet.

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for how to get set up and test multiplayer changes locally.

## License

Released under the [MIT License](LICENSE).
