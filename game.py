"""
Combined launcher for Car Game.

One window, one process. Pick Single Player or Online Multiplayer from the
main menu; each mode stays in its own module and can be left back to the menu.
"""

import pygame as pg

import highscores as hs
from online_game import OnlineGame
from singleplayer import SinglePlayerGame

SCREEN_W, SCREEN_H = 640, 640


class CarGame:
    def __init__(self, start_mode="menu"):
        pg.init()
        self.screen = pg.display.set_mode((SCREEN_W, SCREEN_H))
        pg.display.set_caption("Car Game")
        self.clock = pg.time.Clock()

        self.font = pg.font.Font(None, 36)
        self.font_big = pg.font.Font(None, 60)
        self.font_small = pg.font.Font(None, 28)
        self.font_tiny = pg.font.Font(None, 22)

        self.background = pg.transform.scale(
            pg.image.load("background.png").convert(), (SCREEN_W, SCREEN_H))
        self.bg_y = 0

        self.running = True
        self.mode = "menu"       # "menu" | "single" | "online"
        self.single = None
        self.online = None
        self.best_single = hs.best_score("single")
        self.best_online = hs.best_score("online")

        if start_mode == "single":
            self._start_single()

    # -------------------------------------------------------------------
    # Main loop
    # -------------------------------------------------------------------
    def run(self):
        while self.running:
            dt = self.clock.tick(60) / 1000.0
            dt = max(0.001, dt)
            events = pg.event.get()

            for event in events:
                if event.type == pg.QUIT:
                    self.running = False
            if not self.running:
                break

            if self.mode == "menu":
                self._update_menu(events)
            elif self.mode == "single" and self.single:
                if self.single.update(events, dt) == "menu":
                    self.single = None
                    self.mode = "menu"
                    self._refresh_bests()
            elif self.mode == "online" and self.online:
                self.online.step(events, dt)
                if not self.online.running:
                    self.running = False
                elif self.online.exit_to_launcher:
                    self.online._cleanup()
                    self.online = None
                    self.mode = "menu"
                    self._refresh_bests()

            pg.display.flip()

        if self.online:
            self.online._cleanup()
        pg.quit()

    # -------------------------------------------------------------------
    # Main menu
    # -------------------------------------------------------------------
    def _update_menu(self, events):
        self.bg_y = (self.bg_y + 1) % SCREEN_H
        self.screen.blit(self.background, (0, self.bg_y))
        self.screen.blit(self.background, (0, self.bg_y - SCREEN_H))

        overlay = pg.Surface((SCREEN_W, SCREEN_H), pg.SRCALPHA)
        overlay.fill((10, 12, 28, 170))
        self.screen.blit(overlay, (0, 0))

        title = self.font_big.render("CAR GAME", True, (255, 255, 255))
        self.screen.blit(title, (SCREEN_W // 2 - title.get_width() // 2, 65))

        subtitle = self.font_small.render("Choose a mode", True, (160, 190, 230))
        self.screen.blit(subtitle, (SCREEN_W // 2 - subtitle.get_width() // 2, 135))

        single_btn = pg.Rect(170, 235, 300, 58)
        online_btn = pg.Rect(170, 315, 300, 58)
        quit_btn = pg.Rect(250, 500, 140, 44)

        mx, my = pg.mouse.get_pos()
        self._draw_button(single_btn, "Single Player", (0, 150, 80),
                          single_btn.collidepoint(mx, my), self.font)
        self._draw_button(online_btn, "Online Multiplayer", (40, 80, 180),
                          online_btn.collidepoint(mx, my), self.font)
        self._draw_button(quit_btn, "Quit", (150, 40, 40),
                          quit_btn.collidepoint(mx, my), self.font_small)

        best_single = self.font_tiny.render(
            f"Single-player best: {self.best_single}", True, (200, 220, 200))
        self.screen.blit(best_single, (SCREEN_W // 2 - best_single.get_width() // 2, 405))

        best_online = self.font_tiny.render(
            f"Online best: {self.best_online}", True, (200, 210, 235))
        self.screen.blit(best_online, (SCREEN_W // 2 - best_online.get_width() // 2, 430))

        hint = self.font_tiny.render(
            "Press 1 or 2 to choose  •  ESC to quit", True, (150, 150, 170))
        self.screen.blit(hint, (SCREEN_W // 2 - hint.get_width() // 2, 575))

        for event in events:
            if event.type == pg.KEYDOWN:
                if event.key in (pg.K_1, pg.K_KP1):
                    self._start_single()
                elif event.key in (pg.K_2, pg.K_KP2):
                    self._start_online()
                elif event.key == pg.K_ESCAPE:
                    self.running = False
            elif event.type == pg.MOUSEBUTTONDOWN:
                if single_btn.collidepoint(mx, my):
                    self._start_single()
                elif online_btn.collidepoint(mx, my):
                    self._start_online()
                elif quit_btn.collidepoint(mx, my):
                    self.running = False

    # -------------------------------------------------------------------
    # Mode switching
    # -------------------------------------------------------------------
    def _start_single(self):
        self.single = SinglePlayerGame(self.screen, self.clock)
        self.single.enter()
        self.mode = "single"

    def _start_online(self):
        if self.online:
            self.online._cleanup()
        self.online = OnlineGame(self.screen, self.clock, embedded=True)
        self.mode = "online"

    def _refresh_bests(self):
        self.best_single = hs.best_score("single")
        self.best_online = hs.best_score("online")

    def _draw_button(self, rect, text, color, hover=False, font=None):
        font = font or self.font
        fill = tuple(min(255, channel + 35) for channel in color) if hover else color
        pg.draw.rect(self.screen, fill, rect, border_radius=10)
        if hover:
            pg.draw.rect(self.screen, (255, 255, 255), rect, 2, border_radius=10)
        surf = font.render(text, True, (255, 255, 255))
        self.screen.blit(surf, (rect.centerx - surf.get_width() // 2,
                                rect.centery - surf.get_height() // 2))


if __name__ == "__main__":
    CarGame().run()
