import pygame as pg
import random

pg.init()
bg_y = 0
screen = pg.display.set_mode((640,640))
begin_game = ("READY?", "GO!")
clock = pg.time.Clock()
delta_time = 0.1
car = pg.Rect(190,360,35,75)
car_img = pg.image.load("redcar.png")
car_img = pg.transform.scale(car_img, (30, 80))

green_car = pg.image.load("enemy.png")
blue_car = pg.image.load("enemy2.png")

car_types = [
    pg.transform.scale(green_car, (40, 80)),
    pg.transform.scale(blue_car, (40, 80))
]

game_over = False
obstacles = []
scored_obstacles = set()
score = 0
paused = False
font = pg.font.Font(None, 36)
background = pg.image.load("background.png")
background = pg.transform.scale(background, (640, 640))
LANES = [
    (118, 220),   # lane 1 range
    (222, 316),   # lane 2 range
    (317, 418),   # lane 3 range
    (419, 525),   # lane 4 range
]

high_score = 0

def reset_game():
    global car, obstacles, score, scored_obstacles, game_over
    car.topleft = (190, 360)
    obstacles.clear()
    scored_obstacles.clear()
    score = 0
    game_over = False

running = True
do_countdown = False

def countdown_unpause():
    current_screen = screen.copy()
    for i in range(2):
        screen.blit(current_screen, (0, 0))
        countdown_txt = font.render(begin_game[i], True, (255, 255, 255))
        screen.blit(countdown_txt, (270, 300))
        pg.display.flip()
        pg.time.wait(1000)

while running:    

    delta_time = clock.tick(60) / 1000
    delta_time = max(0.001, delta_time)

    for event in pg.event.get():
        if event.type == pg.QUIT:
            running = False
        if event.type == pg.KEYDOWN:
            if event.key == pg.K_ESCAPE:
                if paused:
                    do_countdown = True
                paused = not paused
        if event.type == pg.MOUSEBUTTONDOWN:
            if game_over:
                if retry_btn.collidepoint(pg.mouse.get_pos()):
                    reset_game()
                if quit_btn.collidepoint(pg.mouse.get_pos()):
                    running = False

    if not paused and not game_over:

        bg_y += min(3 + (score //20), 15)  # same speed as cars
        if bg_y >= 640:
            bg_y = 0

        screen.blit(background, (0, bg_y))
        screen.blit(background, (0, bg_y - 640))


        keys = pg.key.get_pressed()
        if keys[pg.K_DOWN] and car.bottom < 640:
            car.y += 5
        if keys[pg.K_UP] and car.top > 0:
            car.y -= 5
        if keys[pg.K_LEFT] and car.left > 105:
            car.x -= 5
        if keys[pg.K_RIGHT] and car.right < 535:
            car.x += 5 
        
        spawn_rate = min(0.02 + (score * 0.002),0.1)
        if random.random() < spawn_rate:
            lane_range = random.choice(LANES)
            lane = random.randint(lane_range[0],lane_range[1])
            min_gap_y = 200
            min_gap_x = 85
            too_close = any(abs(obs[0].x - lane) < min_gap_x and obs[0].y < min_gap_y for obs in obstacles)
            if not too_close:
                img = random.choice(car_types)
                obstacles.append((pg.Rect(lane , -40, 35, 70), img))

        for obs, image in obstacles[:]:
            obs.y += min(4 + (score //20), 15)
            screen.blit(image, obs)
            if obs.top > car.bottom and id(obs) not in scored_obstacles:
                score += 1
                scored_obstacles.add(id(obs))
            if obs.top > 640:
                scored_obstacles.discard(id(obs))
                obstacles.remove((obs, image))
            if car.colliderect(obs):
                if high_score < score:
                    high_score = score
                game_over = True                
        screen.blit(car_img,car)

    elif not game_over:
        screen.blit(background, (0, bg_y))
        screen.blit(background, (0, bg_y - 640))        
        for obs, image in obstacles:
            screen.blit(image, obs)
        screen.blit(car_img,car)
        overlay = pg.Surface((640, 640))
        overlay.set_alpha(150)
        overlay.fill((0, 0, 0))
        screen.blit(overlay, (0, 0))
        if not do_countdown:
            pause_txt = font.render("PAUSED", True, (255, 255, 255))
            screen.blit(pause_txt, (270, 300))
    
    if do_countdown:
        do_countdown = False
        countdown_unpause()

    score_txt = font.render(f"Score: {score}", True, (255, 255, 255), (0, 0, 0,))
    screen.blit(score_txt, (10, 590)) 
    high_score_txt = font.render(f"High Score {high_score}", True, (255, 255, 255), (0, 0, 0,))
    screen.blit(high_score_txt, (10, 615))
    

    if game_over:
        screen.blit(background, (0, bg_y))
        screen.blit(background, (0, bg_y - 640))
        overlay = pg.Surface((640, 640))
        overlay.set_alpha(150)
        overlay.fill((0, 0, 0))
        screen.blit(overlay, (0, 0))

        game_over_txt = font.render("GAME OVER", True, (255, 255, 255))
        screen.blit(game_over_txt, (250, 250))

        retry_btn = pg.Rect(200, 300, 100, 40)
        pg.draw.rect(screen, (0, 200, 0), retry_btn)
        retry_txt = font.render("Retry", True, (255, 255, 255))
        screen.blit(retry_txt, (220, 310))

        quit_btn = pg.Rect(340, 300, 100, 40)
        pg.draw.rect(screen, (200, 0, 0), quit_btn)
        quit_txt = font.render("Quit", True, (255, 255, 255))
        screen.blit(quit_txt, (362, 310))


        score_txt = font.render(f"Score: {score}", True, (255, 255, 255))
        screen.blit(score_txt, (202, 350))
        high_score_txt = font.render(f"High Score: {high_score}", True, (255, 255, 255))
        screen.blit(high_score_txt, (342, 350))


    pg.display.flip()

pg.quit()