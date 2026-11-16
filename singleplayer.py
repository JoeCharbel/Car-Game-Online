"""
Single-player mode.

Kept separate from the online game so either mode can be driven by the
combined launcher (game.py) inside one window and one process.
"""

import random

import pygame as pg

import highscores as hs
from paths import resource_path

SCREEN_W, SCREEN_H = 640, 640
LANES = [
    (118, 220),   # lane 1 range
    (222, 316),   # lane 2 range
    (317, 418),   # lane 3 range
    (419, 525),   # lane 4 range
]
CAR_W, CAR_H = 30, 80
BUS_W, BUS_H = 48, 98
OBSTACLE_LANE_GAP = 28
BUS_SPAWN_CHANCE = 0.06
BUS_SPEED_BONUS = 3.0

# Traffic sprites, same set as the online mode: two normal cars and a rare,
# faster bus. key, file, render size, extra pixels per frame.
ENEMY_FILES = [
    ("enemy_green", "enemy.png", (40, 80), 0.0),
    ("enemy_blue", "enemy2.png", (40, 80), 0.0),
    ("enemy_bus", "enemy_bus.png", (BUS_W, BUS_H), BUS_SPEED_BONUS),
]


class SinglePlayerGame:
    def __init__(self, screen, clock):
        self.screen = screen
        self.clock = clock

        self.font = pg.font.Font(None, 36)
        self.font_small = pg.font.Font(None, 26)
        self.font_tiny = pg.font.Font(None, 22)

        self.background = pg.transform.scale(
            pg.image.load(resource_path("background.png")).convert(),
            (SCREEN_W, SCREEN_H))
        self.car_img = pg.transform.scale(
            pg.image.load(resource_path("redcar.png")).convert_alpha(), (CAR_W, CAR_H))
        self.enemy_assets = {
            key: {
                "surface": pg.transform.scale(
                    pg.image.load(resource_path(path)).convert_alpha(), size),
                "size": size,
                "speed_bonus": bonus,
            }
            for key, path, size, bonus in ENEMY_FILES
        }
        self.default_enemy_keys = ["enemy_green", "enemy_blue"]

        self.high_score = hs.best_score("single")
        self.reset()

    # -------------------------------------------------------------------
    # Setup
    # -------------------------------------------------------------------
    def enter(self):
        """Called when the mode is opened from the main menu."""
        self.high_score = hs.best_score("single")
        self.reset()

    def reset(self):
        self.car = pg.Rect(190, 360, 35, 75)
        self.obstacles = []
        self.scored = set()
        self.score = 0
        self.bg_y = 0
        self.game_over = False
        self.paused = False
        self.score_saved = False
        self.last_rank = None

    # -------------------------------------------------------------------
    # Traffic (mirrors the online mode so both play the same)
    # -------------------------------------------------------------------
    def _choose_enemy_key(self):
        """Pick a standard traffic car most of the time, with a rare fast bus."""
        if random.random() < BUS_SPAWN_CHANCE:
            return "enemy_bus"
        return random.choice(self.default_enemy_keys)

    def _can_spawn_obstacle(self, spawn_rect, lane_idx):
        """Keep new traffic from spawning into occupied space near the top."""
        for obstacle in self.obstacles:
            if obstacle["lane_idx"] != lane_idx:
                continue
            if spawn_rect.colliderect(obstacle["rect"].inflate(24, 220)):
                return False
        return True

    def _obstacle_speed(self, obstacle, base_speed):
        """Pixels this vehicle wants to cover this frame."""
        return base_speed + obstacle.get("speed_bonus", 0.0)

    def _move_obstacles_with_spacing(self, base_speed):
        """
        Advance traffic, keeping at least OBSTACLE_LANE_GAP between vehicles.

        Each vehicle moves at its own speed (the bus is faster). A faster
        vehicle that catches the one in front follows at that vehicle's pace
        instead of driving through it, so a lane never overlaps.
        """
        lanes = {}
        for obstacle in self.obstacles:
            lanes.setdefault(obstacle.get("lane_idx", -1), []).append(obstacle)

        for lane_obstacles in lanes.values():
            # Front of the lane first: the largest y is closest to the player.
            lane_obstacles.sort(key=lambda item: item["rect"].y, reverse=True)
            vehicle_ahead = None
            for obstacle in lane_obstacles:
                rect = obstacle["rect"]
                rect.y += self._obstacle_speed(obstacle, base_speed)
                if vehicle_ahead is not None:
                    # Close the gap, never overlap the vehicle ahead.
                    rect.y = min(rect.y, vehicle_ahead - OBSTACLE_LANE_GAP - rect.height)
                vehicle_ahead = rect.y

    # -------------------------------------------------------------------
    # Update / draw
    # -------------------------------------------------------------------
    def update(self, events, dt):
        """Advance the mode. Returns 'menu' when the player wants to leave."""
        if self.game_over:
            return self._update_game_over(events)
        if self.paused:
            return self._update_paused(events)
        return self._update_playing(events, dt)

    def _update_playing(self, events, dt):
        for event in events:
            if event.type == pg.KEYDOWN and event.key == pg.K_ESCAPE:
                self.paused = True
                return None

        scroll_speed = min(3 + (self.score // 20), 15)
        self.bg_y = (self.bg_y + scroll_speed) % SCREEN_H
        self.screen.blit(self.background, (0, self.bg_y))
        self.screen.blit(self.background, (0, self.bg_y - SCREEN_H))

        keys = pg.key.get_pressed()
        if keys[pg.K_DOWN] and self.car.bottom < SCREEN_H:
            self.car.y += 5
        if keys[pg.K_UP] and self.car.top > 0:
            self.car.y -= 5
        if keys[pg.K_LEFT] and self.car.left > 105:
            self.car.x -= 5
        if keys[pg.K_RIGHT] and self.car.right < 535:
            self.car.x += 5

        spawn_rate = min(0.02 + (self.score * 0.002), 0.1)
        if random.random() < spawn_rate:
            lane_idx = random.randrange(len(LANES))
            lane_start, lane_end = LANES[lane_idx]
            enemy_key = self._choose_enemy_key()
            size = self.enemy_assets[enemy_key]["size"]
            lane_x_max = max(lane_start, lane_end - size[0])
            spawn_rect = pg.Rect(
                random.randint(lane_start, lane_x_max), -size[1], size[0], size[1])
            if self._can_spawn_obstacle(spawn_rect, lane_idx):
                self.obstacles.append({
                    "rect": spawn_rect,
                    "img_key": enemy_key,
                    "lane_idx": lane_idx,
                    "speed_bonus": self.enemy_assets[enemy_key]["speed_bonus"],
                })

        self._move_obstacles_with_spacing(min(4 + (self.score // 20), 15))
        for obstacle in self.obstacles[:]:
            rect = obstacle["rect"]
            self.screen.blit(self.enemy_assets[obstacle["img_key"]]["surface"], rect)

            if (not self.game_over and rect.top > self.car.bottom
                    and id(obstacle) not in self.scored):
                self.score += 1
                self.scored.add(id(obstacle))

            if rect.top > SCREEN_H:
                self.scored.discard(id(obstacle))
                self.obstacles.remove(obstacle)

            if not self.game_over and self.car.colliderect(rect):
                self._crash()

        self.screen.blit(self.car_img, self.car)
        self._draw_hud()
        return None

    def _crash(self):
        if self.game_over:
            return
        if self.high_score < self.score:
            self.high_score = self.score
        if not self.score_saved:
            if self.score > 0:
                self.last_rank, _ = hs.add_score("single", "You", self.score)
                self.high_score = max(self.high_score, hs.best_score("single"))
            self.score_saved = True
        self.game_over = True

    # -------------------------------------------------------------------
    # Pause screen
    # -------------------------------------------------------------------
    def _update_paused(self, events):
        self.screen.blit(self.background, (0, self.bg_y))
        self.screen.blit(self.background, (0, self.bg_y - SCREEN_H))
        for obstacle in self.obstacles:
            self.screen.blit(self.enemy_assets[obstacle["img_key"]]["surface"],
                             obstacle["rect"])
        self.screen.blit(self.car_img, self.car)

        overlay = pg.Surface((SCREEN_W, SCREEN_H), pg.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        title = self.font.render("PAUSED", True, (255, 255, 255))
        self.screen.blit(title, (SCREEN_W // 2 - title.get_width() // 2, 205))

        resume_btn = pg.Rect(200, 280, 240, 48)
        menu_btn = pg.Rect(200, 345, 240, 48)
        mx, my = pg.mouse.get_pos()
        self._draw_button(resume_btn, "Resume", (0, 150, 80),
                          resume_btn.collidepoint(mx, my))
        self._draw_button(menu_btn, "Main Menu", (50, 90, 180),
                          menu_btn.collidepoint(mx, my))

        hint = self.font_tiny.render("ESC or Enter to resume", True, (190, 190, 190))
        self.screen.blit(hint, (SCREEN_W // 2 - hint.get_width() // 2, 420))

        for event in events:
            if event.type == pg.KEYDOWN and event.key in (pg.K_ESCAPE, pg.K_RETURN):
                self.paused = False
            elif event.type == pg.MOUSEBUTTONDOWN:
                if resume_btn.collidepoint(mx, my):
                    self.paused = False
                elif menu_btn.collidepoint(mx, my):
                    return "menu"
        return None

    # -------------------------------------------------------------------
    # Game over screen
    # -------------------------------------------------------------------
    def _update_game_over(self, events):
        self.screen.blit(self.background, (0, self.bg_y))
        self.screen.blit(self.background, (0, self.bg_y - SCREEN_H))

        overlay = pg.Surface((SCREEN_W, SCREEN_H), pg.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        self.screen.blit(overlay, (0, 0))

        title = self.font.render("GAME OVER", True, (255, 255, 255))
        self.screen.blit(title, (SCREEN_W // 2 - title.get_width() // 2, 250))

        retry_btn = pg.Rect(200, 300, 100, 40)
        menu_btn = pg.Rect(330, 300, 160, 40)
        mx, my = pg.mouse.get_pos()
        self._draw_button(retry_btn, "Retry", (0, 160, 80),
                          retry_btn.collidepoint(mx, my))
        self._draw_button(menu_btn, "Main Menu", (50, 90, 180),
                          menu_btn.collidepoint(mx, my))

        score_txt = self.font.render(f"Score: {self.score}", True, (255, 255, 255))
        self.screen.blit(score_txt, (202, 350))
        high_txt = self.font.render(f"High Score: {self.high_score}", True, (255, 255, 255))
        self.screen.blit(high_txt, (342, 350))

        top_runs = hs.top_scores("single", 5)
        if top_runs:
            top_label = self.font_small.render("TOP RUNS", True, (220, 220, 255))
            self.screen.blit(top_label, (SCREEN_W // 2 - top_label.get_width() // 2, 392))
            for index, entry in enumerate(top_runs):
                line = f"{index + 1}.  {entry['name']}  —  {entry['score']}"
                color = (255, 215, 0) if index == 0 else (205, 205, 205)
                line_surf = self.font_small.render(line, True, color)
                self.screen.blit(
                    line_surf, (SCREEN_W // 2 - line_surf.get_width() // 2,
                                418 + index * 24))

        if self.last_rank == 1:
            new_best = self.font_small.render("NEW HIGH SCORE!", True, (255, 215, 0))
            self.screen.blit(new_best, (SCREEN_W // 2 - new_best.get_width() // 2, 558))

        hint = self.font_tiny.render("Enter to retry  •  ESC for main menu", True, (180, 180, 190))
        self.screen.blit(hint, (SCREEN_W // 2 - hint.get_width() // 2, 600))

        for event in events:
            if event.type == pg.KEYDOWN:
                if event.key == pg.K_RETURN:
                    self.reset()
                    return None
                if event.key == pg.K_ESCAPE:
                    return "menu"
            elif event.type == pg.MOUSEBUTTONDOWN:
                if retry_btn.collidepoint(mx, my):
                    self.reset()
                    return None
                if menu_btn.collidepoint(mx, my):
                    return "menu"
        return None

    # -------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------
    def _draw_hud(self):
        score_txt = self.font.render(f"Score: {self.score}", True, (255, 255, 255), (0, 0, 0))
        self.screen.blit(score_txt, (10, 588))

        high_txt = self.font_tiny.render(
            f"High Score: {self.high_score}", True, (230, 230, 230), (0, 0, 0))
        self.screen.blit(high_txt, (10, 618))

        hint = self.font_tiny.render("ESC Pause", True, (200, 200, 200), (0, 0, 0))
        self.screen.blit(hint, (SCREEN_W - hint.get_width() - 10, 618))

    def _draw_button(self, rect, text, color, hover=False):
        fill = tuple(min(255, channel + 35) for channel in color) if hover else color
        pg.draw.rect(self.screen, fill, rect, border_radius=8)
        if hover:
            pg.draw.rect(self.screen, (255, 255, 255), rect, 2, border_radius=8)
        surf = self.font.render(text, True, (255, 255, 255))
        self.screen.blit(surf, (rect.centerx - surf.get_width() // 2,
                                rect.centery - surf.get_height() // 2))
