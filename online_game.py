"""
Online multiplayer mode: host a game or join one by IP.

Run through game.py for the mode menu, or run this file directly:

    python online_game.py
"""

import pygame as pg
import random
import time as _time
import math
from network import GameServer, GameClient
from paths import resource_path
import highscores as hs

# ---------------------------------------------------------------------------
# Constants (shared with singleplayer.py so both modes play the same)
# ---------------------------------------------------------------------------
SCREEN_W, SCREEN_H = 640, 640
LANES = [
    (118, 220),
    (222, 316),
    (317, 418),
    (419, 525),
]
CAR_W, CAR_H = 30, 80
OBS_W, OBS_H = 35, 70
BUS_W, BUS_H = 48, 98
PORT = 5555
OBSTACLE_LANE_GAP = 28
BUS_SPAWN_CHANCE = 0.06
# The bus is the fast vehicle. It wants this many extra pixels per frame and
# follows the car in front when it catches up, so traffic never overlaps.
BUS_SPEED_BONUS = 3.0

# Shared road speed. The host is the only one who advances the clock, every
# screen receives the same speed so traffic lines up on all machines.
BASE_SPEED = 4.0
MAX_SPEED = 15.0
SPEED_RAMP_TICKS = 900.0     # frames to go from BASE_SPEED to MAX_SPEED
WORLD_STATE_INTERVAL = 4     # broadcast authoritative traffic every N ticks
WINNER_RESULTS_DELAY = 5.0   # seconds of victory lap before results

# Player palette for UI and sprite assignment
PLAYER_COLORS = [
    (255, 60, 60),     # red (local default feel)
    (60, 120, 255),    # blue
    (60, 220, 60),     # green
    (255, 200, 40),    # yellow
    (200, 60, 255),    # purple
    (255, 140, 40),    # orange
    (40, 220, 220),    # cyan
    (255, 100, 180),   # pink
]

PLAYER_CAR_FILES = [
    "redcar.png",
    "player_blue.png",
    "player_green.png",
    "player_yellow.png",
    "player_purple.png",
    "player_orange.png",
    "player_cyan.png",
    "player_pink.png",
]

# States
STATE_MENU = 0
STATE_LOBBY = 1
STATE_COUNTDOWN = 2
STATE_PLAYING = 3
STATE_GAMEOVER = 4


class OnlineGame:
    def __init__(self, screen=None, clock=None, embedded=False):
        pg.init()
        self.embedded = embedded
        self.exit_to_launcher = False
        self.screen = (screen if screen is not None
                       else pg.display.set_mode((SCREEN_W, SCREEN_H)))
        if screen is None:
            pg.display.set_caption("Car Game — Online Multiplayer")
        self.clock = clock if clock is not None else pg.time.Clock()

        # Fonts
        self.font = pg.font.Font(None, 36)
        self.font_big = pg.font.Font(None, 60)
        self.font_small = pg.font.Font(None, 28)
        self.font_tiny = pg.font.Font(None, 22)

        # Assets
        self.background = pg.transform.scale(pg.image.load(resource_path("background.png")).convert(), (SCREEN_W, SCREEN_H))
        self.car_img = self._load_scaled_alpha("redcar.png", (CAR_W, CAR_H))
        self.player_car_imgs = {
            i: self._load_scaled_alpha(path, (CAR_W, CAR_H))
            for i, path in enumerate(PLAYER_CAR_FILES)
        }
        self.enemy_assets = {
            'enemy_green': {
                'surface': self._load_scaled_alpha("enemy.png", (40, 80)),
                'size': (OBS_W, OBS_H),
                'speed_bonus': 0,
            },
            'enemy_blue': {
                'surface': self._load_scaled_alpha("enemy2.png", (40, 80)),
                'size': (OBS_W, OBS_H),
                'speed_bonus': 0,
            },
            'enemy_bus': {
                'surface': self._load_scaled_alpha("enemy_bus.png", (BUS_W, BUS_H)),
                'size': (BUS_W, BUS_H),
                'speed_bonus': BUS_SPEED_BONUS,
            },
        }
        self.default_enemy_keys = ['enemy_green', 'enemy_blue']

        # Game state
        self.state = STATE_MENU
        self.is_host = False
        self.server = None
        self.client = None
        self.my_id = 0
        self.my_name = ""
        self.players = {}       # pid -> {name, ready, alive, x, y, color_idx, score}
        self.obstacles = []     # [{id, rect, img_key, lane_idx, speed_bonus}]
        self.next_obs_id = 0
        self.score = 0
        self.bg_y = 0
        self.winner_name = ""
        self.game_tick = 0

        # Elimination flow
        self.elimination_choice = None  # None, 'spectate', or 'leave'
        self.winner_announced = ""      # set when 1 player remains
        self.spectating = False         # joined mid-round, or chose to watch
        self.eliminated_local = False   # local crash already applied

        # Shared round state
        self.world_speed = BASE_SPEED
        self.results_at = 0.0           # winner was announced at this time
        self.score_saved = False
        self.score_rank = None
        self.my_best = hs.best_score('online')

        # Car rect for local player
        self.car = pg.Rect(190, 360, CAR_W - 5, CAR_H - 5)

        # UI input
        self.input_text = ""
        self.input_active = False
        self.name_text = "Player"
        self.name_active = False
        self.active_field = None  # 'ip' or 'name'
        self.status_msg = ""
        self.status_time = 0

        # Obstacle RNG seed (host sets this)
        self.rng = random.Random()

        self.running = True

    def _load_scaled_alpha(self, path, size):
        """Load an image with alpha preserved and scale it to the requested size."""
        return pg.transform.scale(
            pg.image.load(resource_path(path)).convert_alpha(), size)

    def _get_player_color_idx(self, pid):
        """Resolve the assigned sprite index for a player."""
        return self.players.get(pid, {}).get('color_idx', pid) % len(self.player_car_imgs)

    def _draw_text_input(self, rect, text, active):
        """Draw a text box with a blinking caret when it is focused."""
        border_color = (100, 180, 255) if active else (100, 100, 130)
        pg.draw.rect(self.screen, border_color, rect, 2)

        text_surf = self.font_small.render(text, True, (255, 255, 255))
        text_y = rect.y + (rect.height - text_surf.get_height()) // 2
        self.screen.blit(text_surf, (rect.x + 8, text_y))

        if active and (pg.time.get_ticks() // 500) % 2 == 0:
            caret_x = rect.x + 8 + text_surf.get_width() + 2
            caret_top = rect.y + 6
            caret_bottom = rect.bottom - 6
            pg.draw.line(self.screen, (255, 255, 255), (caret_x, caret_top), (caret_x, caret_bottom), 2)

    def _choose_enemy_key(self):
        """Pick a standard traffic car most of the time, with a rare fast bus."""
        if self.rng.random() < BUS_SPAWN_CHANCE:
            return 'enemy_bus'
        return self.rng.choice(self.default_enemy_keys)

    def _can_spawn_obstacle(self, spawn_rect, lane_idx):
        """Keep new traffic from spawning into occupied space near the top of a lane."""
        for obstacle in self.obstacles:
            if obstacle.get('lane_idx') != lane_idx:
                continue
            if spawn_rect.colliderect(obstacle['rect'].inflate(24, 220)):
                return False
        return True

    def _obstacle_speed(self, obstacle, base_speed):
        """Pixels this vehicle wants to cover this frame."""
        return base_speed + obstacle.get('speed_bonus', 0.0)

    def _move_obstacles_with_spacing(self, base_speed):
        """
        Advance traffic, keeping at least OBSTACLE_LANE_GAP between vehicles.

        Each vehicle moves at its own speed (the bus is faster). A faster
        vehicle that catches the one in front follows at that vehicle's pace
        instead of driving through it, so a lane never overlaps.
        """
        lanes = {}
        for obstacle in self.obstacles:
            lanes.setdefault(obstacle.get('lane_idx', -1), []).append(obstacle)

        for lane_obstacles in lanes.values():
            # Front of the lane first: the largest y is closest to the player.
            lane_obstacles.sort(key=lambda item: item['rect'].y, reverse=True)
            vehicle_ahead = None
            for obstacle in lane_obstacles:
                rect = obstacle['rect']
                rect.y += self._obstacle_speed(obstacle, base_speed)
                if vehicle_ahead is not None:
                    # Close the gap, never overlap the vehicle ahead.
                    rect.y = min(rect.y, vehicle_ahead - OBSTACLE_LANE_GAP - rect.height)
                vehicle_ahead = rect.y

    # -------------------------------------------------------------------
    # Shared world / player elimination helpers
    # -------------------------------------------------------------------
    def _obstacle_payload(self):
        """Serializable snapshot of the host's traffic."""
        return [{
            'id': obstacle['id'],
            'x': obstacle['rect'].x,
            'y': obstacle['rect'].y,
            'img_key': obstacle['img_key'],
            'lane_idx': obstacle['lane_idx'],
            'speed_bonus': obstacle['speed_bonus'],
        } for obstacle in self.obstacles]

    def _broadcast_world_state(self):
        """Host sends the authoritative road speed and traffic positions."""
        if not self.is_host or not self.server:
            return
        self.server.broadcast({
            'type': 'WORLD_STATE',
            'speed': self.world_speed,
            'obstacles': self._obstacle_payload(),
        })

    def _apply_world_state(self, obstacle_data):
        """Reconcile locally simulated traffic with the host's snapshot."""
        snapshot = {}
        for item in obstacle_data:
            obs_id = item.get('id')
            if obs_id is not None:
                snapshot[obs_id] = item

        kept_ids = set()
        for obstacle in self.obstacles[:]:
            item = snapshot.get(obstacle['id'])
            if item is None:
                # The host no longer has this car (off-screen / round reset).
                self.obstacles.remove(obstacle)
                continue
            kept_ids.add(obstacle['id'])
            if abs(obstacle['rect'].y - item.get('y', obstacle['rect'].y)) > 10:
                # Only snap when drift is visible, so normal movement stays smooth.
                obstacle['rect'].y = item['y']
            obstacle['rect'].x = item.get('x', obstacle['rect'].x)
            # Keep the lane and speed the host simulates with; the local
            # spacing pass reads both, so a stale value would desync traffic.
            obstacle['lane_idx'] = item.get('lane_idx', obstacle['lane_idx'])
            obstacle['speed_bonus'] = item.get('speed_bonus', obstacle['speed_bonus'])

        for obs_id, item in snapshot.items():
            if obs_id in kept_ids:
                continue
            img_key = item.get('img_key', 'enemy_green')
            size = self.enemy_assets.get(img_key, {}).get('size', (OBS_W, OBS_H))
            self.obstacles.append({
                'id': obs_id,
                'rect': pg.Rect(item.get('x', 0), item.get('y', -size[1]), size[0], size[1]),
                'img_key': img_key,
                'lane_idx': item.get('lane_idx', 0),
                'speed_bonus': item.get('speed_bonus', 0),
            })

    def _local_player_crashed(self):
        """Apply the local crash immediately, then let the host confirm it."""
        info = self.players.get(self.my_id)
        if not info or not info.get('alive', False):
            return

        info['alive'] = False
        info['score'] = self.score
        self.eliminated_local = True
        self.elimination_choice = None

        if self.is_host:
            self._broadcast_player_states()
            self._check_game_end()
        elif self.client:
            self.client.send({
                'type': 'PLAYER_ELIMINATED',
                'player_id': self.my_id,
                'score': self.score,
            })

    def _host_check_collisions(self):
        """
        Host decides crashes for every driver.

        Clients still show a crash instantly, but the host is the final
        authority, so a laggy player cannot drive through traffic.
        """
        if not self.is_host:
            return

        newly_dead = False
        for pid, info in self.players.items():
            if info.get('spectator') or not info.get('alive', False):
                continue
            player_rect = pg.Rect(
                info.get('x', 0), info.get('y', 0), CAR_W - 5, CAR_H - 5)
            for obstacle in self.obstacles:
                if player_rect.colliderect(obstacle['rect']):
                    info['alive'] = False
                    if pid == self.my_id:
                        info['score'] = self.score
                    newly_dead = True
                    break

        if newly_dead:
            self._broadcast_player_states()
            self._check_game_end()

    def _save_my_score(self):
        """Persist the local player's score once per round."""
        if self.score_saved or self.spectating:
            return
        self.score_saved = True
        if self.score <= 0:
            return
        try:
            self.score_rank, _ = hs.add_score('online', self.my_name or 'Player', self.score)
        except (OSError, ValueError):
            self.score_rank = None
        self.my_best = hs.best_score('online')

    def _draw_live_standings(self):
        """Compact scoreboard in the top-right corner."""
        players = [
            (pid, info) for pid, info in self.players.items()
            if not info.get('spectator')
        ]
        if len(players) < 2:
            return
        players.sort(key=lambda item: item[1].get('score', 0), reverse=True)
        players = players[:5]

        panel = pg.Surface((210, 10 + len(players) * 22), pg.SRCALPHA)
        panel.fill((0, 0, 0, 120))
        x = SCREEN_W - panel.get_width() - 8
        self.screen.blit(panel, (x, 8))

        y = 13
        for pid, info in players:
            color_idx = self._get_player_color_idx(pid)
            color = PLAYER_COLORS[color_idx % len(PLAYER_COLORS)]
            if not info.get('alive', False):
                color = (130, 130, 130)
            name = info.get('name', 'Player')
            if pid == self.my_id:
                name += ' (You)'
            line = f"{name[:14]}  {info.get('score', 0)}"
            surf = self.font_tiny.render(line, True, color)
            self.screen.blit(surf, (x + 8, y))
            y += 22

    # -------------------------------------------------------------------
    # Main loop
    # -------------------------------------------------------------------
    def step(self, events, dt):
        """Run one frame. Used by both the standalone loop and the launcher."""
        for event in events:
            if event.type == pg.QUIT:
                self.running = False

        if self.state == STATE_MENU:
            self._update_menu(events)
        elif self.state == STATE_LOBBY:
            self._update_lobby(events)
        elif self.state == STATE_COUNTDOWN:
            self._update_countdown(events)
        elif self.state == STATE_PLAYING:
            self._update_playing(events, dt)
        elif self.state == STATE_GAMEOVER:
            self._update_gameover(events)

    def run(self):
        while self.running:
            dt = self.clock.tick(60) / 1000.0
            dt = max(0.001, dt)
            self.step(pg.event.get(), dt)
            pg.display.flip()

        self._cleanup()
        pg.quit()

    # -------------------------------------------------------------------
    # MENU
    # -------------------------------------------------------------------
    def _update_menu(self, events):
        self.screen.fill((20, 20, 35))

        # Title
        title = self.font_big.render("CAR GAME ONLINE", True, (255, 255, 255))
        self.screen.blit(title, (SCREEN_W // 2 - title.get_width() // 2, 80))

        subtitle = self.font_small.render("Peer-to-Peer Multiplayer", True, (150, 150, 200))
        self.screen.blit(subtitle, (SCREEN_W // 2 - subtitle.get_width() // 2, 140))

        # Name input
        name_label = self.font_small.render("Your Name:", True, (200, 200, 200))
        self.screen.blit(name_label, (170, 200))
        name_box = pg.Rect(300, 195, 180, 32)
        self._draw_text_input(name_box, self.name_text, self.active_field == 'name')

        # Host button
        host_btn = pg.Rect(200, 280, 240, 50)
        pg.draw.rect(self.screen, (0, 150, 80), host_btn, border_radius=8)
        host_txt = self.font.render("Host Game", True, (255, 255, 255))
        self.screen.blit(host_txt, (host_btn.centerx - host_txt.get_width() // 2,
                                     host_btn.centery - host_txt.get_height() // 2))

        # Join button
        join_btn = pg.Rect(200, 360, 240, 50)
        pg.draw.rect(self.screen, (40, 80, 180), join_btn, border_radius=8)
        join_txt = self.font.render("Join Game", True, (255, 255, 255))
        self.screen.blit(join_txt, (join_btn.centerx - join_txt.get_width() // 2,
                                     join_btn.centery - join_txt.get_height() // 2))

        # IP input (for joining)
        ip_label = self.font_small.render("Host IP:", True, (200, 200, 200))
        self.screen.blit(ip_label, (170, 440))
        ip_box = pg.Rect(260, 435, 210, 32)
        self._draw_text_input(ip_box, self.input_text, self.active_field == 'ip')

        # Status message
        if self.status_msg and _time.time() - self.status_time < 4:
            status_surf = self.font_small.render(self.status_msg, True, (255, 100, 100))
            self.screen.blit(status_surf, (SCREEN_W // 2 - status_surf.get_width() // 2, 520))

        # Back / Quit button
        quit_btn = pg.Rect(230, 555, 180, 40)
        pg.draw.rect(self.screen, (150, 30, 30), quit_btn, border_radius=8)
        quit_label = "Main Menu" if self.embedded else "Quit"
        quit_txt = self.font_small.render(quit_label, True, (255, 255, 255))
        self.screen.blit(quit_txt, (quit_btn.centerx - quit_txt.get_width() // 2,
                                     quit_btn.centery - quit_txt.get_height() // 2))

        for event in events:
            if event.type == pg.MOUSEBUTTONDOWN:
                mx, my = pg.mouse.get_pos()
                if name_box.collidepoint(mx, my):
                    self.active_field = 'name'
                elif ip_box.collidepoint(mx, my):
                    self.active_field = 'ip'
                elif host_btn.collidepoint(mx, my):
                    self._host_game()
                elif join_btn.collidepoint(mx, my):
                    self._join_game()
                elif quit_btn.collidepoint(mx, my):
                    if self.embedded:
                        self._exit_to_launcher()
                    else:
                        self.running = False
                else:
                    self.active_field = None

            if event.type == pg.KEYDOWN:
                if self.active_field == 'name':
                    if event.key == pg.K_BACKSPACE:
                        self.name_text = self.name_text[:-1]
                    elif event.key == pg.K_RETURN:
                        self.active_field = None
                    elif event.key == pg.K_TAB:
                        self.active_field = 'ip'
                    elif len(self.name_text) < 15 and event.unicode.isprintable():
                        self.name_text += event.unicode
                elif self.active_field == 'ip':
                    if event.key == pg.K_BACKSPACE:
                        self.input_text = self.input_text[:-1]
                    elif event.key == pg.K_RETURN:
                        self._join_game()
                    elif event.key == pg.K_TAB:
                        self.active_field = 'name'
                    elif len(self.input_text) < 45 and event.unicode.isprintable():
                        self.input_text += event.unicode

    def _host_game(self):
        """Start as the host."""
        name = self.name_text.strip() or "Host"
        self.my_name = name
        self.is_host = True
        self.my_id = 0
        self.spectating = False
        self.eliminated_local = False
        self.score_saved = False
        self.score_rank = None
        self.winner_announced = ""
        self.winner_name = ""
        self.results_at = 0.0
        self.world_speed = BASE_SPEED
        self.server = GameServer(PORT)
        try:
            self.server.start()
        except OSError as e:
            self.status_msg = f"Failed to start server: {e}"
            self.status_time = _time.time()
            self.server = None
            return
        # Host player info
        self.players = {
            0: {'name': name, 'ready': False, 'alive': True,
                'x': 190, 'y': 360, 'color_idx': 0, 'score': 0}
        }
        self.state = STATE_LOBBY

    def _join_game(self):
        """Join an existing game."""
        host_ip = self.input_text.strip()
        if not host_ip:
            self.status_msg = "Enter the host IP address!"
            self.status_time = _time.time()
            return
        name = self.name_text.strip() or "Player"
        self.my_name = name
        self.is_host = False
        self.spectating = False
        self.eliminated_local = False
        self.score_saved = False
        self.score_rank = None
        self.winner_announced = ""
        self.winner_name = ""
        self.results_at = 0.0
        self.world_speed = BASE_SPEED
        self.client = GameClient()
        if self.client.connect(host_ip, PORT, name):
            self.my_id = self.client.player_id
            self.players = {}
            self.state = STATE_LOBBY
        else:
            self.status_msg = "Could not connect to host!"
            self.status_time = _time.time()
            self.client = None

    # -------------------------------------------------------------------
    # LOBBY
    # -------------------------------------------------------------------
    def _update_lobby(self, events):
        self._process_network()

        self.screen.fill((20, 25, 45))

        # Title
        lobby_title = self.font_big.render("LOBBY", True, (255, 255, 255))
        self.screen.blit(lobby_title, (SCREEN_W // 2 - lobby_title.get_width() // 2, 30))

        if self.is_host:
            # Get host IP to display
            try:
                hostname = __import__('socket').gethostbyname(__import__('socket').gethostname())
            except Exception:
                hostname = "unknown"
            ip_txt = self.font_small.render(f"Your IP: {hostname}  |  Port: {PORT}", True, (150, 200, 150))
            self.screen.blit(ip_txt, (SCREEN_W // 2 - ip_txt.get_width() // 2, 90))

        mode_txt = self.font_small.render(
            "You are the HOST" if self.is_host else "Connected to host",
            True, (100, 200, 255))
        self.screen.blit(mode_txt, (SCREEN_W // 2 - mode_txt.get_width() // 2, 115))

        # Player list
        y_offset = 160
        players_label = self.font.render("Players:", True, (220, 220, 220))
        self.screen.blit(players_label, (80, y_offset))
        y_offset += 40

        for pid, info in sorted(self.players.items()):
            color_idx = info.get('color_idx', pid % len(PLAYER_COLORS))
            color = PLAYER_COLORS[color_idx % len(PLAYER_COLORS)]
            is_me = (pid == self.my_id)
            name_str = info['name'] + (" (You)" if is_me else "")
            ready_str = " ✓ READY" if info.get('ready', False) else ""
            txt_color = (100, 255, 100) if info.get('ready', False) else (220, 220, 220)

            # Color dot
            pg.draw.circle(self.screen, color, (100, y_offset + 12), 8)
            ptxt = self.font_small.render(f"  {name_str}{ready_str}", True, txt_color)
            self.screen.blit(ptxt, (115, y_offset))
            y_offset += 35

        # Ready button
        my_ready = self.players.get(self.my_id, {}).get('ready', False)
        ready_btn = pg.Rect(200, 460, 240, 45)
        btn_color = (150, 60, 60) if my_ready else (0, 150, 80)
        pg.draw.rect(self.screen, btn_color, ready_btn, border_radius=8)
        ready_label = "Cancel Ready" if my_ready else "Ready!"
        ready_surf = self.font.render(ready_label, True, (255, 255, 255))
        self.screen.blit(ready_surf, (ready_btn.centerx - ready_surf.get_width() // 2,
                                       ready_btn.centery - ready_surf.get_height() // 2))

        # Start button (host only, only when all ready and >= 2 players)
        start_btn = None
        if self.is_host:
            all_ready = all(p.get('ready', False) for p in self.players.values())
            enough = len(self.players) >= 2
            can_start = all_ready and enough
            start_btn = pg.Rect(200, 520, 240, 45)
            btn_col = (0, 120, 200) if can_start else (60, 60, 80)
            pg.draw.rect(self.screen, btn_col, start_btn, border_radius=8)
            start_surf = self.font.render("Start Game", True, (255, 255, 255) if can_start else (120, 120, 120))
            self.screen.blit(start_surf, (start_btn.centerx - start_surf.get_width() // 2,
                                           start_btn.centery - start_surf.get_height() // 2))

        # Leave button
        leave_btn = pg.Rect(20, 590, 100, 35)
        pg.draw.rect(self.screen, (130, 30, 30), leave_btn, border_radius=6)
        leave_surf = self.font_small.render("Leave", True, (255, 255, 255))
        self.screen.blit(leave_surf, (leave_btn.centerx - leave_surf.get_width() // 2,
                                       leave_btn.centery - leave_surf.get_height() // 2))

        # Status
        if self.status_msg and _time.time() - self.status_time < 4:
            st = self.font_small.render(self.status_msg, True, (255, 200, 100))
            self.screen.blit(st, (SCREEN_W // 2 - st.get_width() // 2, 590))

        for event in events:
            if event.type == pg.MOUSEBUTTONDOWN:
                mx, my = pg.mouse.get_pos()
                if ready_btn.collidepoint(mx, my):
                    self._toggle_ready()
                if start_btn and start_btn.collidepoint(mx, my) and self.is_host:
                    self._try_start_game()
                if leave_btn.collidepoint(mx, my):
                    self._leave_lobby()

    def _toggle_ready(self):
        """Toggle ready status for local player."""
        if self.my_id in self.players:
            self.players[self.my_id]['ready'] = not self.players[self.my_id]['ready']
        else:
            self.players[self.my_id] = {
                'name': self.my_name, 'ready': True, 'alive': True,
                'x': 190, 'y': 360, 'color_idx': self.my_id % len(PLAYER_COLORS), 'score': 0
            }

        if self.is_host:
            self._broadcast_lobby_state()
        else:
            self.client.send({
                'type': 'PLAYER_READY',
                'ready': self.players.get(self.my_id, {}).get('ready', False)
            })

    def _try_start_game(self):
        """Host tries to start the game."""
        if not self.is_host:
            return
        all_ready = all(p.get('ready', False) for p in self.players.values())
        if len(self.players) < 2 or not all_ready:
            self.status_msg = "Need 2+ players, all ready!"
            self.status_time = _time.time()
            return
        # Generate a seed for synchronized RNG
        seed = random.randint(0, 2**31)
        self.rng = random.Random(seed)
        self.game_tick = 0
        self.next_obs_id = 0
        self.world_speed = BASE_SPEED
        self.winner_announced = ""
        self.winner_name = ""
        self.results_at = 0.0
        self.spectating = False
        self.eliminated_local = False
        self.score_saved = False
        self.score_rank = None
        # Reset all players
        start_positions = self._get_start_positions(len(self.players))
        idx = 0
        for pid in sorted(self.players.keys()):
            self.players[pid]['alive'] = True
            self.players[pid]['score'] = 0
            self.players[pid]['spectator'] = False
            self.players[pid]['x'] = start_positions[idx][0]
            self.players[pid]['y'] = start_positions[idx][1]
            idx += 1
        # Set local car
        my_info = self.players[self.my_id]
        self.car.topleft = (my_info['x'], my_info['y'])
        self.score = 0
        self.obstacles.clear()
        self.bg_y = 0
        self.elimination_choice = None

        self.server.broadcast({
            'type': 'START_GAME',
            'seed': seed,
            'speed': BASE_SPEED,
            'players': {str(k): v for k, v in self.players.items()},
        })
        self.state = STATE_COUNTDOWN
        self.countdown_start = _time.time()

    def _get_start_positions(self, n):
        """Get evenly spaced starting positions for n players."""
        positions = []
        lane_centers = [169, 269, 367, 472]
        for i in range(n):
            lx = lane_centers[i % len(lane_centers)]
            positions.append((lx, 360))
        return positions

    def _broadcast_lobby_state(self):
        """Host broadcasts current lobby state to all clients."""
        if not self.is_host:
            return
        self.server.broadcast({
            'type': 'LOBBY_STATE',
            'players': {str(k): v for k, v in self.players.items()},
        })

    def _leave_lobby(self):
        """Leave the lobby and return to menu."""
        self._cleanup()
        self.state = STATE_MENU
        self.players.clear()
        self.obstacles.clear()
        self.spectating = False
        self.eliminated_local = False
        self.score_saved = False
        self.score_rank = None
        self.winner_announced = ""
        self.winner_name = ""
        self.results_at = 0.0
        self.world_speed = BASE_SPEED

    def _exit_to_launcher(self):
        """Close the online session and return to the combined main menu."""
        self._cleanup()
        self.players.clear()
        self.obstacles.clear()
        self.exit_to_launcher = True

    # -------------------------------------------------------------------
    # COUNTDOWN
    # -------------------------------------------------------------------
    def _update_countdown(self, events):
        self._process_network()

        elapsed = _time.time() - self.countdown_start
        self.screen.blit(self.background, (0, 0))

        # Draw all player cars at starting positions
        for pid, info in self.players.items():
            if info.get('spectator'):
                continue
            img = self._get_car_img(pid)
            self.screen.blit(img, (info['x'], info['y']))

        # Overlay
        overlay = pg.Surface((SCREEN_W, SCREEN_H), pg.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        self.screen.blit(overlay, (0, 0))

        # Countdown text
        if elapsed < 1:
            txt = "3"
        elif elapsed < 2:
            txt = "2"
        elif elapsed < 3:
            txt = "1"
        elif elapsed < 4:
            txt = "GO!"
        else:
            self.state = STATE_PLAYING
            return

        count_surf = self.font_big.render(txt, True, (255, 255, 100))
        self.screen.blit(count_surf, (SCREEN_W // 2 - count_surf.get_width() // 2,
                                       SCREEN_H // 2 - count_surf.get_height() // 2))

    # -------------------------------------------------------------------
    # PLAYING
    # -------------------------------------------------------------------
    def _update_playing(self, events, dt):
        self._process_network()
        now = _time.time()

        # The host owns the round clock and the shared road speed. Every
        # machine receives the same speed, so traffic no longer drifts apart.
        if self.is_host:
            self.game_tick += 1
            self.world_speed = min(
                BASE_SPEED + self.game_tick / SPEED_RAMP_TICKS, MAX_SPEED)

        my_info = self.players.get(self.my_id)
        my_alive = bool(my_info and my_info.get('alive', False)) and not self.spectating

        # --- Scroll background ---
        self.bg_y = (self.bg_y + self.world_speed) % SCREEN_H

        self.screen.blit(self.background, (0, self.bg_y))
        self.screen.blit(self.background, (0, self.bg_y - SCREEN_H))

        # --- Input (only if alive and actually in the round) ---
        if my_alive:
            keys = pg.key.get_pressed()
            if keys[pg.K_DOWN] and self.car.bottom < SCREEN_H:
                self.car.y += 5
            if keys[pg.K_UP] and self.car.top > 0:
                self.car.y -= 5
            if keys[pg.K_LEFT] and self.car.left > 105:
                self.car.x -= 5
            if keys[pg.K_RIGHT] and self.car.right < 535:
                self.car.x += 5

            # Update my position in players dict
            my_info['x'] = self.car.x
            my_info['y'] = self.car.y
            my_info['score'] = self.score

        # --- Host: spawn obstacles ---
        if self.is_host:
            spawn_rate = min(0.02 + (self.game_tick * 0.0003), 0.1)
            if self.rng.random() < spawn_rate:
                lane_idx = self.rng.randrange(len(LANES))
                lane_range = LANES[lane_idx]
                enemy_key = self._choose_enemy_key()
                enemy_asset = self.enemy_assets[enemy_key]
                obs_w, obs_h = enemy_asset['size']
                lane_x_max = max(lane_range[0], lane_range[1] - obs_w)
                lane_x = self.rng.randint(lane_range[0], lane_x_max)
                obs_rect = pg.Rect(lane_x, -obs_h, obs_w, obs_h)
                if self._can_spawn_obstacle(obs_rect, lane_idx):
                    obs_id = self.next_obs_id
                    self.next_obs_id += 1
                    self.obstacles.append({
                        'id': obs_id,
                        'rect': obs_rect,
                        'img_key': enemy_key,
                        'lane_idx': lane_idx,
                        'speed_bonus': enemy_asset['speed_bonus'],
                    })
                    self.server.broadcast({
                        'type': 'OBSTACLE_SPAWN',
                        'obs_id': obs_id,
                        'x': lane_x,
                        'y': -obs_h,
                        'w': obs_w,
                        'h': obs_h,
                        'img_key': enemy_key,
                        'lane_idx': lane_idx,
                        'speed_bonus': enemy_asset['speed_bonus'],
                    })

        # --- Move obstacles (same speed everywhere) ---
        self._move_obstacles_with_spacing(self.world_speed)
        for o in self.obstacles[:]:
            asset = self.enemy_assets[o['img_key']]
            self.screen.blit(asset['surface'], o['rect'])

            # Score: obstacle passed below car
            if my_alive and o['rect'].top > self.car.bottom and not o.get('scored'):
                self.score += 1
                o['scored'] = True

            # Remove off-screen
            if o['rect'].top > SCREEN_H:
                self.obstacles.remove(o)

            # Collision with local player (instant feedback; host confirms)
            if my_alive and self.car.colliderect(o['rect']):
                self._local_player_crashed()
                my_alive = False

        # --- Host: authoritative crashes, sync, and round timer ---
        if self.is_host:
            self._host_check_collisions()
            if self.game_tick % WORLD_STATE_INTERVAL == 0:
                self._broadcast_world_state()
            if self.winner_announced and self.results_at and now >= self.results_at:
                self._finish_game()

        # --- Draw remote players ---
        for pid, info in self.players.items():
            if pid == self.my_id or info.get('spectator'):
                continue
            if info.get('alive', False):
                img = self._get_car_img(pid)
                self.screen.blit(img, (info.get('x', 0), info.get('y', 0)))
            else:
                # Draw a faded explosion or ghost
                img = self._get_car_img(pid)
                ghost = img.copy()
                ghost.set_alpha(60)
                self.screen.blit(ghost, (info.get('x', 0), info.get('y', 0)))

        # --- Draw local player ---
        if not self.spectating:
            local_img = self._get_car_img(self.my_id)
            if my_alive:
                self.screen.blit(local_img, self.car)
            else:
                ghost = local_img.copy()
                ghost.set_alpha(60)
                self.screen.blit(ghost, self.car)

                # --- Elimination choice / spectating UI ---
                if self.elimination_choice is None:
                    # Show choice buttons
                    overlay = pg.Surface((SCREEN_W, 120), pg.SRCALPHA)
                    overlay.fill((0, 0, 0, 160))
                    self.screen.blit(overlay, (0, 10))

                    elim_txt = self.font.render("YOU CRASHED!", True, (255, 80, 80))
                    self.screen.blit(elim_txt, (SCREEN_W // 2 - elim_txt.get_width() // 2, 20))

                    spectate_btn = pg.Rect(140, 60, 160, 42)
                    pg.draw.rect(self.screen, (40, 120, 180), spectate_btn, border_radius=8)
                    spec_surf = self.font.render("Spectate", True, (255, 255, 255))
                    self.screen.blit(spec_surf, (spectate_btn.centerx - spec_surf.get_width() // 2,
                                                  spectate_btn.centery - spec_surf.get_height() // 2))

                    leave_btn = pg.Rect(340, 60, 160, 42)
                    pg.draw.rect(self.screen, (150, 40, 40), leave_btn, border_radius=8)
                    leave_surf = self.font.render("Leave", True, (255, 255, 255))
                    self.screen.blit(leave_surf, (leave_btn.centerx - leave_surf.get_width() // 2,
                                                  leave_btn.centery - leave_surf.get_height() // 2))

                    # Handle clicks on choice buttons
                    for event in events:
                        if event.type == pg.MOUSEBUTTONDOWN:
                            mx, my = pg.mouse.get_pos()
                            if spectate_btn.collidepoint(mx, my):
                                self.elimination_choice = 'spectate'
                            elif leave_btn.collidepoint(mx, my):
                                self._leave_lobby()
                                return
                else:
                    # Spectating
                    spec_txt = self.font.render("ELIMINATED — Spectating", True, (255, 100, 100))
                    self.screen.blit(spec_txt, (SCREEN_W // 2 - spec_txt.get_width() // 2, 20))
        else:
            # Joined while a round was already running
            spec_txt = self.font.render("SPECTATING", True, (255, 210, 100))
            self.screen.blit(spec_txt, (SCREEN_W // 2 - spec_txt.get_width() // 2, 20))
            sub_txt = self.font_small.render(
                "You will join the next round from the lobby", True, (210, 210, 210))
            self.screen.blit(sub_txt, (SCREEN_W // 2 - sub_txt.get_width() // 2, 48))

        # --- Winner announcement banner (during gameplay) ---
        if self.winner_announced:
            if self.results_at:
                remaining = max(0, int(math.ceil(self.results_at - now)))
                banner_label = f"Winner: {self.winner_announced}!  Results in {remaining}s"
            else:
                banner_label = f"Winner: {self.winner_announced}!"
            banner = self.font.render(banner_label, True, (255, 255, 100), (0, 0, 0))
            self.screen.blit(banner, (SCREEN_W // 2 - banner.get_width() // 2, 90))

        # --- HUD ---
        if self.spectating:
            score_txt = self.font.render("Spectating", True, (255, 210, 100), (0, 0, 0))
        else:
            score_txt = self.font.render(f"Score: {self.score}", True, (255, 255, 255), (0, 0, 0))
        self.screen.blit(score_txt, (10, 590))

        # Alive count (spectators do not count towards the round)
        alive_count = sum(
            1 for p in self.players.values()
            if p.get('alive', False) and not p.get('spectator'))
        total_players = sum(1 for p in self.players.values() if not p.get('spectator'))
        alive_txt = self.font_small.render(
            f"Alive: {alive_count}/{total_players}", True, (200, 255, 200), (0, 0, 0))
        self.screen.blit(alive_txt, (10, 615))

        # Live standings (hidden while the crash menu or winner banner is up)
        if (my_alive or self.spectating or self.elimination_choice == 'spectate') \
                and not self.winner_announced:
            self._draw_live_standings()

        # --- Host: broadcast state periodically ---
        if self.is_host and self.game_tick % 3 == 0:
            self._broadcast_player_states()

        # --- Send local position ---
        if my_alive:
            if self.is_host:
                pass  # Host already has its own data
            else:
                self.client.send({
                    'type': 'PLAYER_UPDATE',
                    'player_id': self.my_id,
                    'x': self.car.x,
                    'y': self.car.y,
                    'alive': True,
                    'score': self.score,
                })

    def _get_car_img(self, pid):
        """Get the car image for a given player ID."""
        color_idx = self._get_player_color_idx(pid)
        return self.player_car_imgs.get(color_idx, self.car_img)

    # -------------------------------------------------------------------
    # GAME OVER
    # -------------------------------------------------------------------
    def _update_gameover(self, events):
        self._process_network()
        self._save_my_score()

        self.screen.blit(self.background, (0, self.bg_y))
        self.screen.blit(self.background, (0, self.bg_y - SCREEN_H))

        overlay = pg.Surface((SCREEN_W, SCREEN_H), pg.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        self.screen.blit(overlay, (0, 0))

        # Title
        go_txt = self.font_big.render("GAME OVER", True, (255, 80, 80))
        self.screen.blit(go_txt, (SCREEN_W // 2 - go_txt.get_width() // 2, 45))

        # Winner / Tie
        if self.winner_name == "It's a Tie!":
            winner_txt = self.font.render("It's a Tie!", True, (255, 255, 100))
        else:
            winner_txt = self.font.render(f"Winner: {self.winner_name}!", True, (255, 255, 100))
        self.screen.blit(winner_txt, (SCREEN_W // 2 - winner_txt.get_width() // 2, 115))

        # Personal result + all-time best
        if self.score_rank == 1:
            best_txt = self.font_small.render("NEW ALL-TIME BEST!", True, (255, 215, 0))
        else:
            top = hs.top_scores('online', 1)
            if top:
                best_txt = self.font_small.render(
                    f"All-time best: {top[0]['score']} — {top[0]['name']}",
                    True, (190, 190, 210))
            else:
                best_txt = self.font_small.render("", True, (190, 190, 210))
        self.screen.blit(best_txt, (SCREEN_W // 2 - best_txt.get_width() // 2, 155))

        # Scoreboard
        y = 195
        header = self.font.render("Scoreboard", True, (220, 220, 255))
        self.screen.blit(header, (SCREEN_W // 2 - header.get_width() // 2, y))
        y += 38

        sorted_players = sorted(self.players.items(), key=lambda x: x[1].get('score', 0), reverse=True)
        # Build ranked list with tied positions
        rank = 0
        prev_score = None
        for i, (pid, info) in enumerate(sorted_players):
            p_score = info.get('score', 0)
            if p_score != prev_score:
                rank = i + 1
                prev_score = p_score
            color_idx = info.get('color_idx', pid) % len(PLAYER_COLORS)
            color = PLAYER_COLORS[color_idx]
            me_tag = " (You)" if pid == self.my_id else ""
            spec_tag = " (spectator)" if info.get('spectator') else ""
            line = f"#{rank}  {info['name']}{me_tag}{spec_tag}  —  Score: {p_score}"
            ptxt = self.font_small.render(line, True, color)
            self.screen.blit(ptxt, (SCREEN_W // 2 - ptxt.get_width() // 2, y))
            y += 30

        # Return to lobby button
        lobby_btn = pg.Rect(200, 520, 240, 48)
        pg.draw.rect(self.screen, (40, 100, 180), lobby_btn, border_radius=8)
        lobby_txt = self.font.render("Return to Lobby", True, (255, 255, 255))
        self.screen.blit(lobby_txt, (lobby_btn.centerx - lobby_txt.get_width() // 2,
                                      lobby_btn.centery - lobby_txt.get_height() // 2))

        for event in events:
            if event.type == pg.MOUSEBUTTONDOWN:
                if lobby_btn.collidepoint(pg.mouse.get_pos()):
                    self._return_to_lobby()

    def _return_to_lobby(self):
        """Go back to lobby state, keeping connections alive."""
        # Reset game-specific state
        self.obstacles.clear()
        self.score = 0
        self.bg_y = 0
        self.elimination_choice = None
        self.winner_announced = ""
        self.winner_name = ""
        self.results_at = 0.0
        self.spectating = False
        self.eliminated_local = False
        self.score_saved = False
        self.score_rank = None
        self.world_speed = BASE_SPEED
        self.game_tick = 0
        for pid in self.players:
            self.players[pid]['ready'] = False
            self.players[pid]['alive'] = True
            self.players[pid]['score'] = 0
            self.players[pid]['spectator'] = False

        self.state = STATE_LOBBY

        if self.is_host:
            self.server.broadcast({'type': 'RETURN_TO_LOBBY'})
            self._broadcast_lobby_state()

    # -------------------------------------------------------------------
    # Network processing
    # -------------------------------------------------------------------
    def _process_network(self):
        """Process all pending network messages."""
        if self.is_host:
            self._process_host_messages()
        elif self.client:
            self._process_client_messages()

    def _process_host_messages(self):
        """Host processes messages from clients."""
        if not self.server:
            return

        # Update server's client info with our player list
        for msg_pid, msg in self.server.get_messages():
            msg_type = msg.get('type')

            if msg_type == 'PLAYER_JOINED':
                pid = msg['player_id']
                mid_round = self.state in (STATE_COUNTDOWN, STATE_PLAYING, STATE_GAMEOVER)
                if pid not in self.players:
                    self.players[pid] = {
                        'name': msg.get('name', f'Player {pid}'),
                        'ready': False,
                        'alive': False if mid_round else True,
                        'x': 190,
                        'y': 360,
                        'color_idx': pid % len(PLAYER_COLORS),
                        'score': 0,
                        'spectator': mid_round,
                    }

                # Never drop a late joiner into a live round as a player:
                # they have none of the traffic data. Let them watch instead.
                if self.state == STATE_PLAYING:
                    self.server.send_to(pid, {
                        'type': 'SPECTATE_JOIN',
                        'players': {str(k): v for k, v in self.players.items()},
                        'world_speed': self.world_speed,
                        'obstacles': self._obstacle_payload(),
                    })
                    self._broadcast_player_states()
                elif self.state == STATE_COUNTDOWN:
                    self.server.send_to(pid, {
                        'type': 'SPECTATE_JOIN',
                        'players': {str(k): v for k, v in self.players.items()},
                        'world_speed': BASE_SPEED,
                        'obstacles': [],
                    })
                elif self.state == STATE_GAMEOVER:
                    self.server.send_to(pid, {
                        'type': 'GAME_OVER',
                        'winner': self.winner_name,
                        'players': {str(k): v for k, v in self.players.items()},
                        'spectating': True,
                    })
                else:
                    self._broadcast_lobby_state()

            elif msg_type == 'PLAYER_DISCONNECTED':
                pid = msg.get('player_id', msg_pid)
                disc_name = self.players.get(pid, {}).get('name', '???')
                self.players.pop(pid, None)
                self.status_msg = f"{disc_name} disconnected"
                self.status_time = _time.time()
                if self.state in (STATE_COUNTDOWN, STATE_PLAYING):
                    self._check_game_end()
                    self._broadcast_player_states()
                else:
                    self._broadcast_lobby_state()

            elif msg_type == 'PLAYER_READY':
                pid = msg.get('_from', msg_pid)
                if pid in self.players:
                    self.players[pid]['ready'] = msg.get('ready', False)
                self._broadcast_lobby_state()

            elif msg_type == 'PLAYER_UPDATE':
                pid = msg.get('player_id', msg.get('_from', msg_pid))
                if pid in self.players:
                    self.players[pid]['x'] = msg.get('x', self.players[pid].get('x', 0))
                    self.players[pid]['y'] = msg.get('y', self.players[pid].get('y', 0))
                    self.players[pid]['score'] = msg.get('score', 0)

            elif msg_type == 'PLAYER_ELIMINATED':
                pid = msg.get('player_id', msg.get('_from', msg_pid))
                eliminated = False
                if pid in self.players and not self.players[pid].get('spectator'):
                    if self.players[pid].get('alive', False):
                        self.players[pid]['alive'] = False
                        eliminated = True
                    # The client may have scored a little more before its
                    # report arrived, so always keep the best known score.
                    self.players[pid]['score'] = max(
                        self.players[pid].get('score', 0), msg.get('score', 0))
                if eliminated:
                    self._check_game_end()
                    self._broadcast_player_states()

    def _process_client_messages(self):
        """Client processes messages from the host."""
        if not self.client:
            return

        for msg in self.client.get_messages():
            msg_type = msg.get('type')

            if msg_type == 'DISCONNECTED':
                self.status_msg = "Disconnected from host!"
                self.status_time = _time.time()
                self.state = STATE_MENU
                self._cleanup()
                return

            elif msg_type == 'LOBBY_STATE':
                players_raw = msg.get('players', {})
                self.players = {}
                for k, v in players_raw.items():
                    self.players[int(k)] = v

            elif msg_type == 'START_GAME':
                seed = msg.get('seed', 0)
                self.rng = random.Random(seed)
                self.game_tick = 0
                self.next_obs_id = 0
                self.world_speed = msg.get('speed', BASE_SPEED)
                self.winner_announced = ""
                self.winner_name = ""
                self.results_at = 0.0
                self.spectating = False
                self.eliminated_local = False
                self.score_saved = False
                self.score_rank = None
                players_raw = msg.get('players', {})
                self.players = {}
                for k, v in players_raw.items():
                    self.players[int(k)] = v
                # Set local car position
                my_info = self.players.get(self.my_id, {})
                self.car.topleft = (my_info.get('x', 190), my_info.get('y', 360))
                self.score = 0
                self.obstacles.clear()
                self.bg_y = 0
                self.elimination_choice = None
                self.state = STATE_COUNTDOWN
                self.countdown_start = _time.time()

            elif msg_type == 'SPECTATE_JOIN':
                players_raw = msg.get('players', {})
                self.players = {int(k): v for k, v in players_raw.items()}
                self.world_speed = msg.get('world_speed', BASE_SPEED)
                self.obstacles.clear()
                self._apply_world_state(msg.get('obstacles', []))
                self.spectating = True
                self.eliminated_local = True
                self.elimination_choice = 'spectate'
                self.score = 0
                self.score_saved = True
                self.score_rank = None
                self.winner_announced = ""
                self.results_at = 0.0
                self.state = STATE_PLAYING

            elif msg_type == 'OBSTACLE_SPAWN':
                obs_rect = pg.Rect(msg['x'], msg['y'], msg.get('w', OBS_W), msg.get('h', OBS_H))
                self.obstacles.append({
                    'id': msg['obs_id'],
                    'rect': obs_rect,
                    'img_key': msg.get('img_key', 'enemy_green'),
                    'lane_idx': msg.get('lane_idx', 0),
                    'speed_bonus': msg.get('speed_bonus', 0),
                })

            elif msg_type == 'WORLD_STATE':
                self.world_speed = msg.get('speed', self.world_speed)
                self._apply_world_state(msg.get('obstacles', []))

            elif msg_type == 'PLAYER_STATES':
                players_data = msg.get('players', {})
                for k, v in players_data.items():
                    pid = int(k)
                    if pid == self.my_id:
                        # Only update alive status from server for self, and
                        # never undo a crash we already showed locally.
                        if pid in self.players and not self.eliminated_local:
                            self.players[pid]['alive'] = v.get(
                                'alive', self.players[pid].get('alive', True))
                        continue
                    if pid in self.players:
                        self.players[pid].update(v)
                    else:
                        self.players[pid] = v

            elif msg_type == 'GAME_OVER':
                self.winner_name = msg.get('winner', '???')
                if msg.get('spectating'):
                    self.spectating = True
                # Update final scores
                players_data = msg.get('players', {})
                for k, v in players_data.items():
                    pid = int(k)
                    if pid in self.players:
                        self.players[pid].update(v)
                    else:
                        self.players[pid] = v
                # Make sure local score is preserved
                if self.my_id in self.players:
                    self.players[self.my_id]['score'] = max(
                        self.players[self.my_id].get('score', 0), self.score)
                self._save_my_score()
                self.state = STATE_GAMEOVER

            elif msg_type == 'WINNER_ANNOUNCED':
                self.winner_announced = msg.get('winner', '')
                delay = float(msg.get('delay', WINNER_RESULTS_DELAY))
                self.results_at = _time.time() + delay

            elif msg_type == 'RETURN_TO_LOBBY':
                self.obstacles.clear()
                self.score = 0
                self.bg_y = 0
                self.elimination_choice = None
                self.winner_announced = ""
                self.winner_name = ""
                self.results_at = 0.0
                self.spectating = False
                self.eliminated_local = False
                self.score_saved = False
                self.score_rank = None
                self.world_speed = BASE_SPEED
                self.game_tick = 0
                for pid in self.players:
                    self.players[pid]['ready'] = False
                    self.players[pid]['alive'] = True
                    self.players[pid]['score'] = 0
                    self.players[pid]['spectator'] = False
                self.state = STATE_LOBBY

    def _broadcast_player_states(self):
        """Host broadcasts all player positions/states."""
        if not self.is_host:
            return
        self.server.broadcast({
            'type': 'PLAYER_STATES',
            'players': {str(k): {
                'name': v.get('name', ''),
                'x': v.get('x', 0),
                'y': v.get('y', 0),
                'alive': v.get('alive', True),
                'score': v.get('score', 0),
                'color_idx': v.get('color_idx', 0),
                'spectator': v.get('spectator', False),
            } for k, v in self.players.items()},
        })

    def _check_game_end(self):
        """
        Host checks if the round is decided.

        When one driver is left, announce them and start a short victory
        lap before the results screen instead of waiting for them to crash.
        """
        # Sync host score before any broadcast
        if self.my_id in self.players:
            self.players[self.my_id]['score'] = self.score

        alive = [
            (pid, info) for pid, info in self.players.items()
            if info.get('alive', False) and not info.get('spectator')
        ]

        if len(alive) == 1 and not self.winner_announced:
            winner_pid, winner_info = alive[0]
            self.winner_announced = winner_info.get('name', '???')
            self.winner_name = self.winner_announced
            self.results_at = _time.time() + WINNER_RESULTS_DELAY
            if self.server:
                self.server.broadcast({
                    'type': 'WINNER_ANNOUNCED',
                    'winner': self.winner_announced,
                    'delay': WINNER_RESULTS_DELAY,
                })
        elif len(alive) == 0:
            self._finish_game()

    def _finish_game(self):
        """End the round, work out the winner, and publish the results."""
        if self.state != STATE_PLAYING:
            return

        scored_players = {
            pid: info for pid, info in self.players.items()
            if not info.get('spectator')
        }
        scores = [info.get('score', 0) for info in scored_players.values()]

        if self.winner_announced:
            self.winner_name = self.winner_announced
        elif len(scores) > 1 and len(set(scores)) == 1:
            self.winner_name = "It's a Tie!"
        elif scored_players:
            best_info = max(scored_players.values(), key=lambda info: info.get('score', 0))
            self.winner_name = best_info.get('name', 'Nobody')
        else:
            self.winner_name = "Nobody"

        self.state = STATE_GAMEOVER
        self._save_my_score()

        if self.is_host and self.server:
            self.server.broadcast({
                'type': 'GAME_OVER',
                'winner': self.winner_name,
                'players': {str(k): v for k, v in self.players.items()},
            })

    # -------------------------------------------------------------------
    # Cleanup
    # -------------------------------------------------------------------
    def _cleanup(self):
        """Clean up network resources."""
        if self.server:
            self.server.stop()
            self.server = None
        if self.client:
            self.client.disconnect()
            self.client = None


# -------------------------------------------------------------------
# Entry point
# -------------------------------------------------------------------
if __name__ == "__main__":
    game = OnlineGame()
    game.run()
