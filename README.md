# 🚗 Car Game Online

A top-down, pixel-art car dodging game built with [pygame](https://www.pygame.org/), with both a **single-player** mode and an **online multiplayer** mode where friends race through traffic together. One player hosts, everyone else joins by IP address.

| Menu | Lobby | Gameplay |
|:---:|:---:|:---:|
| ![Menu](docs/menu.png) | ![Lobby](docs/lobby.png) | ![Gameplay](docs/gameplay.png) |

## Features

- **Single-player** endless dodging with a high score and a pause menu
- **Online multiplayer** over TCP: host/join lobby, ready-up, synchronized traffic and a final scoreboard
- Each player gets a different car colour (8 sprites included)
- Difficulty ramps up as your score grows: faster traffic and more of it
- Rare fast-moving buses in multiplayer
- Crashed? **Spectate** the rest of the round or **leave**
- Includes a script to launch two instances on one machine for local testing

## Requirements

- Python 3.9 or newer (tested on Python 3.12)
- [pygame](https://pypi.org/project/pygame/) 2.0 or newer

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

> ⚠️ **Always run the game from the repository folder.** Images are loaded with relative paths, so launching from another directory will crash with a "file not found" error.

### Single-player

```bash
python main_game.py
```

### Online multiplayer

```bash
python online_game.py
```

Then:

1. **Host:** enter a name and click **Host Game**. Your IP address and the port (`5555`) are shown in the lobby.
2. **Everyone else:** enter a name, type the host's IP into **Host IP**, and click **Join Game** (or press Enter in the IP box).
3. Everyone clicks **Ready!**
4. When **2 or more** players are connected and all are ready, the host clicks **Start Game**.
5. After a 3-2-1-GO countdown, dodge the traffic. Last car standing is announced as the winner; the round ends once everyone has crashed and a scoreboard is shown. Click **Return to Lobby** to play again.

Use `Tab` to switch between the name and IP fields.

## Controls

| Key | Action |
|---|---|
| ⬆️ ⬇️ ⬅️ ➡️ Arrow keys | Drive |
| `Esc` | Pause / resume (single-player only) |
| Mouse | Menus and buttons |

## Playing with friends

**Same Wi-Fi / LAN (easiest).** The host shares the IP shown in the lobby and everyone else joins with it. If the host's firewall prompts you on first launch, allow Python through, or open **inbound TCP port 5555**.

**Over the internet.** The game has no matchmaking server, so the host's machine must be reachable. Two options:

- **Virtual LAN (recommended):** everyone installs a tool such as [Tailscale](https://tailscale.com/), [ZeroTier](https://www.zerotier.com/) or Hamachi. The host gives out their address on that virtual network.
- **Port forwarding:** forward TCP port `5555` on your router to the host machine and share your public IP. There is no authentication, so only do this with people you trust.

## Testing locally (two instances on one machine)

Handy when developing or debugging multiplayer without a second computer.

**Windows:** double-click `test_local.bat`, or run it from a terminal in the repo folder.

**macOS / Linux:**

```bash
./test_local.sh
```

Either script opens two game windows. Then:

- **Instance 1:** click **Host Game**
- **Instance 2:** enter `127.0.0.1` and click **Join Game**
- Click **Ready!** in both, then **Start Game** in the host window

Tip: only the window with keyboard focus receives your key presses, so click on the window you want to drive.

## Project structure

```
car-game-online/
├── main_game.py        # Single-player game
├── online_game.py      # Multiplayer game (menu, lobby, gameplay, game-over screens)
├── network.py          # TCP networking: GameServer, GameClient, message framing
├── test_local.bat      # Launch 2 instances for local testing (Windows)
├── test_local.sh       # Same, for macOS / Linux
├── requirements.txt
├── background.png      # Scrolling road
├── redcar.png          # Player 1 car (also used in single-player)
├── player_*.png        # Player car sprites for other colours
├── enemy.png, enemy2.png            # Traffic cars
├── enemy_bus.png, enemy_bus2.png    # Bus sprites (see Known issues)
└── docs/               # README screenshots
```

## How multiplayer works

The game uses a simple **host/client (star) topology** over TCP on port `5555` (`PORT` in `online_game.py`).

- The **host** runs a `GameServer` in a background thread *and* plays the game itself. Clients connect with a `GameClient`.
- Messages are **JSON objects with a 4-byte length prefix** (`send_msg` / `recv_msg` in `network.py`).
- The **host decides when traffic spawns** and broadcasts each spawn (`OBSTACLE_SPAWN`). Every client then moves that traffic locally, so everyone sees the same cars.
- Each client moves its own car and **reports its position** to the host, which rebroadcasts everyone's state a few times per second.
- Each client **detects its own collisions** and tells the host when it is eliminated. The host announces the winner and ends the round.

| Message | Direction | Purpose |
|---|---|---|
| `JOIN` / `ASSIGN_ID` | client → host / host → client | Handshake and player ID assignment |
| `LOBBY_STATE` | host → all | Player list and ready status |
| `PLAYER_READY` | client → host | Toggle ready |
| `START_GAME` | host → all | Round start, RNG seed, starting positions |
| `OBSTACLE_SPAWN` | host → all | A new traffic vehicle |
| `PLAYER_UPDATE` | client → host | Local car position and score |
| `PLAYER_STATES` | host → all | Everyone's positions, alive status, scores |
| `PLAYER_ELIMINATED` | client → host | This player crashed |
| `WINNER_ANNOUNCED` | host → all | One player left alive |
| `GAME_OVER` | host → all | Round finished, final scores |
| `RETURN_TO_LOBBY` | host → all | Everyone back to the lobby |

## Known issues and limitations

- **Bus sprite:** `enemy_bus.png` has an opaque black block along its bottom edge, which shows up as a black rectangle under buses in-game. `enemy_bus2.png` is a clean version with a transparent background and is currently unused; pointing `online_game.py` at it fixes the glitch.
- **Host leaves = game over for everyone.** There is no host migration or reconnect.
- **The lobby IP can be wrong** on machines with several network adapters (VPNs, virtual machines). It is looked up from the hostname, so if friends can't connect, check your address with `ipconfig` (Windows) or `ip a` / `ifconfig` (macOS/Linux).
- **No cheat protection:** clients report their own positions and collisions and are trusted by the host.
- **Joining mid-round** is not specially handled. Have everyone join before the host starts.
- Only 8 car colours exist, so a 9th player would share a colour.
- The single-player high score is not saved between launches.

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for how to get set up and test multiplayer changes locally.

## License

Released under the [MIT License](LICENSE).
