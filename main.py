"""Ashen Trial - a Dark Souls-inspired pixel-art boss duel made with Pygame."""

from __future__ import annotations

import math
import random
import sys
from dataclasses import dataclass
from pathlib import Path

import pygame


WIDTH, HEIGHT, FPS = 1280, 720, 60
GROUND = 566
LEFT_WALL, RIGHT_WALL = 72, WIDTH - 72
WORLD_WIDTH = 3600
WORLD_LEFT, WORLD_RIGHT = 70, WORLD_WIDTH - 80
BONFIRE_X = 250
FOG_GATE_X = 3380
BOSS_ARENA_LEFT = 3720
BOSS_ARENA_RIGHT = BOSS_ARENA_LEFT + WIDTH
BOSS_SPAWN_X = BOSS_ARENA_LEFT + 930
HOLLOW_SPAWNS = (720, 1190, 1660, 2180, 2760)
HOLLOW_SOULS = 80
HOLLOW_VISION_RANGE = 360
HOLLOW_LOSE_RANGE = 520
HOLLOW_ATTACK_RANGE = 78
HOLLOW_LEASH_RANGE = 330
HOLLOW_ATTACK_DURATION = 1.08
HOLLOW_HURT_DURATION = .36
HOLLOW_STAGGER_DURATION = 1.05
HOLLOW_TRANSITION_DURATION = .11
HOLLOW_HEALTH_BAR_TIME = 3.0
INTERACTION_RANGE = 105
FOG_ENTER_DURATION = 1.35
HEAL_DURATION = 1.45
HEAL_APPLY_TIME = .78
DEATH_ANIMATION_DURATION = 1.15
BOSS_DEATH_DURATION = 2.8
VICTORY_MESSAGE_DELAY = 2.55
ROOT = Path(__file__).parent


def clamp(value, low, high):
    return max(low, min(high, value))


def draw_text(surface, font, value, pos, color=(224, 215, 198), anchor="topleft"):
    image = font.render(value, True, color)
    rect = image.get_rect()
    setattr(rect, anchor, pos)
    shade = font.render(value, True, (4, 4, 6))
    shade_rect = shade.get_rect()
    setattr(shade_rect, anchor, (pos[0] + 2, pos[1] + 3))
    surface.blit(shade, shade_rect)
    surface.blit(image, rect)


def remove_background(frame, player=False):
    frame = frame.convert_alpha()
    pixels = pygame.PixelArray(frame)
    for y in range(frame.get_height()):
        for x in range(frame.get_width()):
            color = frame.unmap_rgb(pixels[x, y])
            bright = max(color.r, color.g, color.b)
            saturation = bright - min(color.r, color.g, color.b)
            if player:
                remove = abs(color.r - 160) < 30 and abs(color.g - 160) < 30 and abs(color.b - 160) < 30
            else:
                remove = color.a < 250
            if remove:
                pixels[x, y] = pygame.Color(color.r, color.g, color.b, 0)
    del pixels
    return frame


class SpriteArt:
    def __init__(self):
        self.hero = self._strips(
            "hero",
            ("idle", "walk", "dodge", "block", "drink", "death", "attack_a", "attack_b", "heavy_a", "heavy_b"),
            1.10,
        )
        self.gundyr = self._strips(
            "gundyr",
            ("idle", "walk", "sweep_a", "sweep_b", "thrust_a", "thrust_b", "slam", "special"),
            1.55,
        )
        self.hollow = self._strips(
            "hollow",
            ("idle", "walk", "run", "attack", "hurt", "stagger", "death"),
            1.05,
            required=False,
        )
        self.estus_icon = self._icon("estus_flask_v1.png", 42)

    @staticmethod
    def _icon(filename, max_size):
        source = pygame.image.load(ROOT / "assets" / "ui" / filename).convert_alpha()
        bounds = source.get_bounding_rect(min_alpha=24)
        source = source.subsurface(bounds).copy()
        scale = min(max_size / source.get_width(), max_size / source.get_height())
        size = (
            max(1, round(source.get_width() * scale)),
            max(1, round(source.get_height() * scale)),
        )
        return pygame.transform.smoothscale(source, size)

    @staticmethod
    def _strips(prefix, animation_names, scale, required=True):
        output = {}
        for name in animation_names:
            independent = ROOT / "assets" / "animations_v5" / f"{prefix}_{name}.png"
            legacy = ROOT / "assets" / "animations_v3" / f"{prefix}_{name}.png"
            path = independent if independent.exists() else legacy
            if not path.exists():
                print(f"Aviso: animação ausente: {independent}")
                if required:
                    raise FileNotFoundError(independent)
                return {}
            strip = pygame.image.load(path).convert_alpha()
            frame_count = 10
            cell_w, cell_h = strip.get_width() // frame_count, strip.get_height()
            frames = []
            for column in range(frame_count):
                frame = strip.subsurface((column * cell_w, 0, cell_w, cell_h)).copy()
                frames.append(pygame.transform.scale_by(frame, scale))
            output[name] = frames
        return output


@dataclass
class Particle:
    pos: pygame.Vector2
    velocity: pygame.Vector2
    color: tuple
    life: float
    radius: float
    gravity: float = 0

    def update(self, dt):
        self.life -= dt
        self.velocity.y += self.gravity * dt
        self.pos += self.velocity * dt
        return self.life > 0

    def draw(self, surface, offset):
        pygame.draw.circle(surface, self.color, self.pos + offset, max(1, int(self.radius * min(1, self.life * 2))))


class Hero:
    def __init__(self, max_hp=110.0, damage_multiplier=1.0):
        self.pos = pygame.Vector2(300, GROUND)
        self.velocity = pygame.Vector2()
        self.facing = 1
        self.hp = self.max_hp = float(max_hp)
        self.damage_multiplier = float(damage_multiplier)
        self.stamina = self.max_stamina = 100.0
        self.flasks = 3
        self.state, self.timer = "idle", 0.0
        self.grounded = True
        self.invulnerable = self.flash = 0.0
        self.hit_done = self.attack_queued = False
        self.heal_applied = self.heal_effect = False
        self.combo, self.combo_window = 0, 0.0
        self.attack_variant = "attack_a"

    def free(self):
        return self.state in ("idle", "walk", "jump", "fall")

    def attack(self, heavy=False):
        if not self.free():
            if self.state == "attack" and self.timer > .2:
                self.attack_queued = True
            return
        cost = 35 if heavy else 18
        if self.stamina < cost:
            return
        self.stamina -= cost
        self.state = "heavy" if heavy else "attack"
        self.timer, self.hit_done, self.attack_queued = 0, False, False
        self.combo = 0 if heavy else (self.combo % 2 + 1 if self.combo_window else 1)
        if heavy:
            self.attack_variant = random.choice(("heavy_a", "heavy_b"))
        else:
            self.attack_variant = "attack_a" if self.combo == 1 else "attack_b"
        self.velocity.x *= .25

    def dodge(self, move):
        if not self.free() or not self.grounded or self.stamina < 27:
            return
        if move:
            self.facing = 1 if move > 0 else -1
        self.stamina -= 27
        self.state, self.timer, self.invulnerable = "dodge", 0, .43
        self.velocity.x = self.facing * 760

    def parry(self):
        if self.free() and self.grounded and self.stamina >= 15:
            self.stamina -= 15
            self.state, self.timer = "parry", 0

    def heal(self):
        if self.free() and self.grounded and self.flasks and self.hp < self.max_hp:
            self.flasks -= 1
            self.state, self.timer = "heal", 0
            self.heal_applied = False
            self.velocity.x = 0
            return True
        return False

    def take_damage(self, damage, direction, attacker_x):
        if self.invulnerable or self.hp <= 0:
            return None
        attacker_side = 1 if attacker_x > self.pos.x else -1
        if self.state == "block" and attacker_side == self.facing:
            stamina_cost = damage * 1.15
            if self.stamina >= stamina_cost:
                self.stamina -= stamina_cost
                self.timer = 0
                self.velocity.x = -self.facing * 72
                return "block"
            self.stamina = 0
            damage *= .55
        self.hp = max(0, self.hp - damage)
        self.state, self.timer, self.invulnerable, self.flash = "hurt", 0, .45, .18
        self.velocity = pygame.Vector2(direction * 260, -250)
        self.grounded = False
        return "hit"

    def update(self, dt, move, jump_pressed, defending, left_bound=LEFT_WALL, right_bound=RIGHT_WALL):
        self.heal_effect = False
        self.timer += dt
        self.invulnerable = max(0, self.invulnerable - dt)
        self.flash = max(0, self.flash - dt)
        self.combo_window = max(0, self.combo_window - dt)
        if self.hp <= 0 and self.state not in ("hurt", "dead"):
            self.state, self.timer = "dead", 0

        if self.state == "dodge":
            self.velocity.x *= .93
            if self.timer > .58:
                self.state, self.timer = "idle", 0
        elif self.state in ("attack", "heavy"):
            duration = .62 if self.state == "attack" else 1.0
            if self.timer > duration:
                queued = self.attack_queued and self.stamina >= 18
                self.combo_window = .3
                self.state, self.timer = "idle", 0
                if queued:
                    self.attack()
        elif self.state == "parry":
            self.velocity.x *= .8
            if self.timer > .48:
                self.state, self.timer = "idle", 0
        elif self.state == "block":
            self.velocity.x *= .65
            if move:
                self.facing = 1 if move > 0 else -1
                self.velocity.x = move * 72
            if not defending or not self.grounded or self.stamina <= 0:
                self.state, self.timer = "idle", 0
        elif self.state == "heal":
            self.velocity.x = 0
            if not self.heal_applied and self.timer >= HEAL_APPLY_TIME:
                self.hp = min(self.max_hp, self.hp + 52)
                self.heal_applied = True
                self.heal_effect = True
            if self.timer >= HEAL_DURATION:
                self.state, self.timer = "idle", 0
        elif self.state == "hurt":
            if self.timer > .48:
                self.state, self.timer = ("idle" if self.hp else "dead"), 0
        elif self.state != "dead":
            if defending and self.grounded:
                if move:
                    self.facing = 1 if move > 0 else -1
                self.state, self.timer = "block", 0
                self.velocity.x *= .5
            elif move:
                self.facing = 1 if move > 0 else -1
                self.velocity.x = move * 250
                if self.grounded:
                    self.state = "walk"
            else:
                if self.grounded:
                    self.velocity.x = 0
                    self.state = "idle"
                else:
                    self.velocity.x *= .9
            if jump_pressed and self.grounded:
                self.velocity.y = -565
                self.grounded = False
                self.state = "jump"

        if self.state not in ("dodge", "attack", "heavy", "parry", "block"):
            self.stamina = min(self.max_stamina, self.stamina + 33 * dt)
        elif self.state == "block":
            self.stamina = min(self.max_stamina, self.stamina + 7 * dt)
        if not self.grounded:
            self.velocity.y += 1460 * dt
            if self.velocity.y > 0 and self.state in ("jump", "idle", "walk"):
                self.state = "fall"
        self.pos += self.velocity * dt
        if self.pos.y >= GROUND:
            self.pos.y, self.velocity.y, self.grounded = GROUND, 0, True
            if self.state in ("jump", "fall"):
                self.state, self.timer = "idle", 0
        self.pos.x = clamp(self.pos.x, left_bound + 28, right_bound - 28)

    def attack_box(self):
        if self.state == "attack" and .23 <= self.timer <= .42:
            reach = 100 if self.attack_variant == "attack_a" else 112
            damage = 15 + self.combo * 2
            hitbox = pygame.Rect(
                self.pos.x + self.facing * 40 - (12 if self.facing < 0 else 0),
                self.pos.y - 91,
                self.facing * reach,
                82,
            )
            hitbox.normalize()
            return hitbox, damage * self.damage_multiplier
        if self.state == "heavy" and .5 <= self.timer <= .72:
            reach = 127 if self.attack_variant == "heavy_a" else 148
            damage = 31 if self.attack_variant == "heavy_a" else 28
            hitbox = pygame.Rect(
                self.pos.x + self.facing * 35 - (18 if self.facing < 0 else 0),
                self.pos.y - 106,
                self.facing * reach,
                100,
            )
            hitbox.normalize()
            return hitbox, damage * self.damage_multiplier
        return None, 0

    def hurt_box(self):
        if self.state == "dead":
            return pygame.Rect(int(self.pos.x - 70), int(self.pos.y - 42), 140, 42)
        return pygame.Rect(int(self.pos.x - 24), int(self.pos.y - 116), 48, 116)

    def parry_active(self):
        return self.state == "parry" and .12 <= self.timer <= .3

    def draw(self, surface, sprites, offset):
        if self.state == "dead":
            name = "death"
        elif self.state in ("attack", "heavy"):
            name = self.attack_variant
        elif self.state == "dodge":
            name = "dodge"
        elif self.state == "heal":
            name = "drink"
        elif self.state in ("block", "parry"):
            name = "block"
        elif self.state == "walk":
            name = "walk"
        else:
            name = "idle"
        frames = sprites[name]
        if self.state == "dodge":
            frame_index = min(len(frames) - 1, int(self.timer / .58 * len(frames)))
        elif self.state == "attack":
            frame_index = min(len(frames) - 1, int(self.timer / .62 * len(frames)))
        elif self.state == "heavy":
            frame_index = min(len(frames) - 1, int(self.timer / 1.0 * len(frames)))
        elif self.state == "heal":
            frame_index = min(len(frames) - 1, int(self.timer / HEAL_DURATION * len(frames)))
        elif self.state == "dead":
            frame_index = min(
                len(frames) - 1,
                int(self.timer / DEATH_ANIMATION_DURATION * len(frames)),
            )
        elif self.state == "block":
            frame_index = min(int(self.timer * 12), 7)
        else:
            speed = 11 if name == "walk" else 6
            frame_index = int(self.timer * speed) % len(frames)
        frame = frames[frame_index]
        if self.facing < 0:
            frame = pygame.transform.flip(frame, True, False)
        if self.flash:
            frame = frame.copy()
            frame.fill((90, 20, 20, 0), special_flags=pygame.BLEND_RGB_ADD)
        pos = self.pos + offset
        shadow = pygame.Rect(0, 0, 116 if self.state == "dead" else 62, 13)
        shadow.center = pos.x, GROUND + 7 + offset.y
        pygame.draw.ellipse(surface, (5, 5, 7), shadow)
        # Every strip keeps two transparent pixels below its ground line.
        # Anchoring the cell at y + 2 places the visible feet exactly at y.
        rect = frame.get_rect(midbottom=(pos.x, pos.y + 2))
        surface.blit(frame, rect)
        if self.state == "parry":
            alpha = int(190 * max(0, 1 - self.timer / .48))
            layer = pygame.Surface((110, 130), pygame.SRCALPHA)
            pygame.draw.arc(layer, (230, 211, 158, alpha), (8, 8, 94, 112), -1.3, 1.3, 4)
            if self.facing < 0:
                layer = pygame.transform.flip(layer, True, False)
            surface.blit(layer, (pos.x - 55, pos.y - 119))


class World:
    """Procedural Cemetery of Ash exploration area and parallax scenery."""

    def __init__(self):
        rng = random.Random(3303)
        painting_path = ROOT / "assets" / "cemetery_ash_v2.png"
        self.painting = None
        if painting_path.exists():
            source = pygame.image.load(painting_path).convert()
            self.painting = pygame.transform.smoothscale(source, (2100, HEIGHT))
            cold_grade = pygame.Surface(self.painting.get_size(), pygame.SRCALPHA)
            cold_grade.fill((24, 31, 43, 34))
            self.painting.blit(cold_grade, (0, 0))
        self.foreground = [
            (x, rng.randint(8, 24), rng.choice((-1, 1)), rng.choice(("root", "grass", "stone")))
            for x in range(100, WORLD_WIDTH, 72)
        ]

    def draw(self, surface, camera_x, time):
        if self.painting:
            scroll_range = self.painting.get_width() - WIDTH
            route_progress = clamp(camera_x / max(1, WORLD_WIDTH - WIDTH), 0, 1)
            surface.blit(self.painting, (-round(scroll_range * route_progress), 0))
        else:
            surface.fill((25, 30, 38))
            for y in range(0, HEIGHT, 12):
                shade = 33 + y // 38
                pygame.draw.rect(surface, (shade, shade + 4, shade + 9), (0, y, WIDTH, 13))

        # Two moving veils give the static painting depth without obscuring it.
        far_fog = pygame.Surface((WIDTH, 160), pygame.SRCALPHA)
        for index in range(7):
            x = ((index * 235 - int(camera_x * .16) + int(time * 7)) % (WIDTH + 330)) - 180
            pygame.draw.ellipse(far_fog, (166, 174, 181, 13), (x, 16 + index % 3 * 24, 330, 68))
        surface.blit(far_fog, (0, GROUND - 245))

        for x, height, direction, kind in self.foreground:
            sx = int(x - camera_x)
            if not -35 < sx < WIDTH + 35:
                continue
            if kind == "root":
                pygame.draw.line(surface, (24, 23, 22), (sx, GROUND + 5), (sx + direction * height * 2, GROUND - height // 2), 3)
                pygame.draw.line(surface, (62, 57, 49), (sx, GROUND + 4), (sx + direction * height, GROUND), 1)
            elif kind == "grass":
                for blade in (-5, 0, 5):
                    pygame.draw.line(surface, (54, 55, 49), (sx + blade, GROUND + 3), (sx + blade + direction * 4, GROUND - height), 1)
            else:
                rock = (
                    (sx - 13, GROUND + 3),
                    (sx - 10, GROUND - height // 3),
                    (sx - 2, GROUND - height),
                    (sx + 9, GROUND - height * 2 // 3),
                    (sx + 15, GROUND + 3),
                )
                pygame.draw.polygon(surface, (37, 38, 38), rock)
                pygame.draw.lines(surface, (83, 81, 75), False, rock[1:4], 1)

        near_fog = pygame.Surface((WIDTH, 92), pygame.SRCALPHA)
        for index in range(8):
            x = ((index * 205 - int(camera_x * .38) - int(time * 12)) % (WIDTH + 280)) - 145
            pygame.draw.ellipse(near_fog, (188, 192, 193, 16), (x, 23 + index % 2 * 19, 285, 48))
        surface.blit(near_fog, (0, GROUND - 58))


class Bonfire:
    def __init__(self, x=BONFIRE_X):
        self.x = x
        sprite_path = ROOT / "assets" / "bonfire_v2.png"
        self.sprite = None
        if sprite_path.exists():
            source = pygame.image.load(sprite_path).convert_alpha()
            self.sprite = pygame.transform.smoothscale(source, (118, 118))

    def near(self, hero):
        return abs(hero.pos.x - self.x) <= INTERACTION_RANGE

    def draw(self, surface, offset, time):
        x = int(self.x + offset.x)
        glow = pygame.Surface((150, 130), pygame.SRCALPHA)
        for radius, alpha in ((62, 7), (44, 12), (28, 20)):
            pygame.draw.ellipse(glow, (235, 103, 28, alpha), (75 - radius, 80 - radius, radius * 2, radius * 1.35))
        surface.blit(glow, (x - 75, GROUND - 112))
        if self.sprite:
            surface.blit(self.sprite, self.sprite.get_rect(midbottom=(x, GROUND + 5)))
        else:
            pygame.draw.ellipse(surface, (10, 9, 9), (x - 47, GROUND - 7, 94, 18))
            pygame.draw.polygon(surface, (210, 76, 24), ((x - 18, GROUND - 8), (x, GROUND - 72), (x + 18, GROUND - 8)))
            pygame.draw.line(surface, (92, 87, 78), (x, GROUND - 15), (x, GROUND - 91), 5)
        for ember in range(5):
            phase = (time * (19 + ember * 2) + ember * 1.7) % 1
            ex = x + math.sin(time * 4 + ember) * (8 + ember * 2)
            ey = GROUND - 30 - phase * (35 + ember * 5)
            pygame.draw.circle(surface, (238, 135 + ember * 9, 47), (round(ex), round(ey)), 1)


class BossFogGate:
    """Animated world-space barrier and the one-shot boss entrance sequence."""

    IDLE = "IDLE"
    PLAYER_NEAR = "PLAYER_NEAR"
    ENTERING = "ENTERING"
    ENTERED = "ENTERED"
    LOCKED = "LOCKED"
    TOP = 218
    WIDTH = 112
    HEIGHT = GROUND - TOP

    def __init__(self, x=FOG_GATE_X, seed=3303):
        self.x = float(x)
        self.state = self.IDLE
        self.elapsed = 0.0
        self.time = 0.0
        self.entry_start_x = self.x - 58
        self.entry_target_x = self.x + 68
        self._completed = False
        self._rng = random.Random(seed)
        self._clouds = self._build_clouds()
        self._transition_clouds = [
            pygame.transform.smoothscale(self._clouds[index], size)
            for index, size in enumerate(((520, 310), (640, 360), (460, 280), (590, 340)))
        ]
        self._canvas = pygame.Surface((176, self.HEIGHT + 36), pygame.SRCALPHA)
        self._transition_layer = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self._motes = [self._new_mote(initial=True) for _ in range(26)]

    @staticmethod
    def _build_clouds():
        """Pre-render soft smoke masses once; only their placement changes."""
        clouds = []
        for width, height, tint in (
            (104, 58, (164, 171, 179)),
            (124, 72, (190, 194, 198)),
            (88, 50, (137, 146, 158)),
            (142, 78, (181, 187, 194)),
        ):
            cloud = pygame.Surface((width, height), pygame.SRCALPHA)
            for inset, alpha in ((0, 11), (6, 20), (13, 34), (20, 52)):
                rect = pygame.Rect(inset, inset // 2, width - inset * 2, height - inset)
                if rect.width > 0 and rect.height > 0:
                    pygame.draw.ellipse(cloud, (*tint, alpha), rect)
            clouds.append(cloud)
        return clouds

    def _new_mote(self, initial=False):
        return {
            "x": self._rng.uniform(-55, 55),
            "y": self._rng.uniform(0, self.HEIGHT) if initial else self.HEIGHT + self._rng.uniform(3, 28),
            "vx": self._rng.uniform(-7, 7),
            "vy": self._rng.uniform(-26, -10),
            "radius": self._rng.choice((1.0, 1.5, 2.0, 3.0)),
            "phase": self._rng.uniform(0, math.tau),
            "alpha": self._rng.randint(32, 88),
        }

    @property
    def entering(self):
        return self.state == self.ENTERING

    @property
    def progress(self):
        return clamp(self.elapsed / FOG_ENTER_DURATION, 0, 1) if self.entering else 0.0

    def reset(self):
        self.state = self.IDLE
        self.elapsed = 0.0
        self._completed = False

    def near(self, hero):
        return abs(hero.pos.x - self.x) <= INTERACTION_RANGE

    def begin(self, hero, sealed=True):
        if not sealed or self.entering or self.state in (self.ENTERED, self.LOCKED) or not self.near(hero):
            return False
        self.state = self.ENTERING
        self.elapsed = 0.0
        self.entry_start_x = min(hero.pos.x, self.x - 48)
        self.entry_target_x = self.x + 68
        self._completed = False
        return True

    def advance(self, dt):
        self.time += dt
        for index, mote in enumerate(self._motes):
            mote["y"] += mote["vy"] * dt
            mote["x"] += (mote["vx"] + math.sin(self.time * 2.1 + mote["phase"]) * 5) * dt
            if mote["y"] < -18 or abs(mote["x"]) > 82:
                self._motes[index] = self._new_mote()

    def update(self, dt, hero, sealed=True):
        self.advance(dt)
        if not sealed:
            self.state = self.ENTERED
            return False
        if self.entering:
            self.elapsed = min(FOG_ENTER_DURATION, self.elapsed + dt)
            progress = self.elapsed / FOG_ENTER_DURATION
            eased = progress * progress * (3 - 2 * progress)
            hero.pos.x = self.entry_start_x + (self.entry_target_x - self.entry_start_x) * eased
            hero.velocity.x = 0
            if progress >= 1 and not self._completed:
                self._completed = True
                self.state = self.ENTERED
                return True
            return False
        self.state = self.PLAYER_NEAR if self.near(hero) else self.IDLE
        return False

    def _draw_arch(self, surface, screen_x):
        # Chunky, irregular masonry keeps the entrance readable as brickwork
        # even behind the animated fog.  Staggered joints avoid two flat posts.
        mortar = (13, 14, 17)
        brick_dark = (31, 31, 34)
        brick_mid = (48, 46, 45)
        brick_light = (72, 66, 61)
        brick_w, brick_h, joint = 18, 13, 2

        for side, pillar_x in ((-1, screen_x - 70), (1, screen_x + 48)):
            pygame.draw.rect(surface, mortar, (pillar_x - 2, self.TOP - 2, 24, self.HEIGHT + 9))
            row = 0
            for y in range(self.TOP, GROUND + 1, brick_h + joint):
                offset = -9 if row % 2 else 0
                for column in range(-1, 3):
                    x = pillar_x + offset + column * (brick_w + joint)
                    # Trim the outer overflow while leaving an uneven silhouette.
                    if x + brick_w <= pillar_x or x >= pillar_x + 22:
                        continue
                    left = max(x, pillar_x)
                    right = min(x + brick_w, pillar_x + 22)
                    width = right - left
                    shade = brick_mid if (row + column + (side > 0)) % 3 else brick_dark
                    pygame.draw.rect(surface, shade, (left, y, width, brick_h))
                    pygame.draw.line(surface, brick_light, (left + 1, y + 1), (right - 2, y + 1), 1)
                    pygame.draw.line(surface, (24, 24, 27), (left, y + brick_h - 1), (right - 1, y + brick_h - 1), 1)
                row += 1

        # Wedge-shaped bricks follow the curve instead of forming a smooth ring.
        arch_center = pygame.Vector2(screen_x, self.TOP + 3)
        inner_radius, outer_radius = 49, 70
        segments = 11
        for index in range(segments):
            angle_a = math.pi + index * math.pi / segments
            angle_b = math.pi + (index + 1) * math.pi / segments
            gap = .025
            points = []
            for radius, angle in (
                (outer_radius, angle_a + gap),
                (outer_radius, angle_b - gap),
                (inner_radius, angle_b - gap),
                (inner_radius, angle_a + gap),
            ):
                points.append((
                    round(arch_center.x + math.cos(angle) * radius),
                    round(arch_center.y + math.sin(angle) * radius),
                ))
            shade = brick_mid if index % 3 else brick_dark
            pygame.draw.polygon(surface, mortar, points)
            inset_points = []
            for radius, angle in (
                (outer_radius - 2, angle_a + gap * 1.7),
                (outer_radius - 2, angle_b - gap * 1.7),
                (inner_radius + 2, angle_b - gap * 1.7),
                (inner_radius + 2, angle_a + gap * 1.7),
            ):
                inset_points.append((
                    round(arch_center.x + math.cos(angle) * radius),
                    round(arch_center.y + math.sin(angle) * radius),
                ))
            pygame.draw.polygon(surface, shade, inset_points)
            pygame.draw.line(surface, brick_light, inset_points[0], inset_points[1], 1)

        # Broad footings visually anchor the old masonry in the ground.
        for footing_x in (screen_x - 75, screen_x + 46):
            pygame.draw.rect(surface, mortar, (footing_x, GROUND - 7, 31, 12))
            pygame.draw.rect(surface, brick_dark, (footing_x + 2, GROUND - 5, 27, 8))
            pygame.draw.line(surface, brick_light, (footing_x + 3, GROUND - 4), (footing_x + 27, GROUND - 4), 1)

    def draw(self, surface, offset, time, sealed=True, foreground=False, world_x=None):
        screen_x = int((self.x if world_x is None else world_x) + offset.x)
        if screen_x < -120 or screen_x > WIDTH + 120:
            return
        if not foreground:
            self._draw_arch(surface, screen_x)
        if not sealed:
            return

        canvas = self._canvas
        canvas.fill((0, 0, 0, 0))
        reaction = math.sin(self.progress * math.pi) if self.entering else 0.0
        layer_indices = (0, 1) if not foreground else (2,)
        for layer in layer_indices:
            speed = (0.55, -0.82, 1.18)[layer]
            opacity = (0.72, 0.92, 1.0)[layer] + reaction * 0.2
            for band in range(8):
                cloud = self._clouds[(band + layer) % len(self._clouds)]
                phase = time * speed + band * 1.17 + layer * 2.3
                x = 88 - cloud.get_width() // 2 + math.sin(phase) * (15 + layer * 5)
                y = -12 + band * 43 + math.sin(phase * .63) * 12
                cloud.set_alpha(min(255, round(255 * opacity)))
                canvas.blit(cloud, (round(x), round(y)))

        if foreground:
            for mote in self._motes:
                x = round(88 + mote["x"] + math.sin(time * 1.7 + mote["phase"]) * 4)
                y = round(mote["y"])
                alpha = min(145, round(mote["alpha"] * (1 + reaction * .55)))
                pygame.draw.circle(canvas, (202, 210, 219, alpha), (x, y), max(1, round(mote["radius"])))
            # Narrow luminous folds suggest depth without making the gate glow.
            for fold in range(4):
                fold_x = 58 + fold * 19 + math.sin(time * (1.1 + fold * .09) + fold) * 7
                points = []
                for y in range(-8, self.HEIGHT + 24, 18):
                    points.append((round(fold_x + math.sin(y * .035 + time * 2 + fold) * 7), y))
                pygame.draw.lines(canvas, (205, 211, 216, 29 + round(reaction * 18)), False, points, 3)

        surface.blit(canvas, (screen_x - 88, self.TOP - 10))

    def draw_transition_overlay(self, surface):
        """Brief cool veil while the actor is physically crossing the gate."""
        if not self.entering:
            return
        pulse = math.sin(self.progress * math.pi)
        layer = self._transition_layer
        layer.fill((8, 11, 16, round(54 * pulse)))
        for index, cloud in enumerate(self._transition_clouds):
            direction = -1 if index % 2 else 1
            x = WIDTH // 2 - cloud.get_width() // 2 + direction * 155
            x += round(math.sin(self.time * (.8 + index * .13) + index * 1.4) * 115)
            y = 65 + index * 105 + round(math.sin(self.time * 1.2 + index) * 35)
            cloud.set_alpha(round((64 + index * 8) * pulse))
            layer.blit(cloud, (x, y))
        surface.blit(layer, (0, 0))


# Backwards-compatible name for code/tests that imported the old gate directly.
FogGate = BossFogGate


class Hollow:
    MAX_HP = 40.0

    def __init__(self, x, strong=False):
        self.spawn_x = float(x)
        self.pos = pygame.Vector2(x, GROUND)
        self.strong = strong
        self.hp = self.max_hp = self.MAX_HP * (1.5 if strong else 1)
        self.damage = 18 if strong else 12
        self.facing = -1
        self.state, self.timer = "idle", 0.0
        self.previous_animation = "idle"
        self.previous_frame = 0
        self.transition_timer = 0.0
        self.idle_duration = random.uniform(.65, 1.25)
        self.attack_cooldown = random.uniform(.15, .45)
        self.health_bar_timer = 0.0
        self.patrol_direction = -1 if int(x) % 2 else 1
        self.hit_done = False
        self.flash = 0.0
        self.rewarded = False

    def animation_name(self, state=None):
        state = self.state if state is None else state
        return {
            "patrol": "walk",
            "chase": "run",
            "dead": "death",
        }.get(state, state)

    def animation_frame(self, animation=None, timer=None):
        animation = self.animation_name() if animation is None else animation
        timer = self.timer if timer is None else timer
        durations = {
            "attack": HOLLOW_ATTACK_DURATION,
            "hurt": HOLLOW_HURT_DURATION,
            "stagger": HOLLOW_STAGGER_DURATION,
            "death": 1.2,
        }
        if animation in durations:
            return min(9, int(timer / durations[animation] * 10))
        speed = 11 if animation == "run" else (8 if animation == "walk" else 4)
        return int(timer * speed) % 10

    def set_state(self, state, *, reset_timer=True):
        if state == self.state:
            return
        self.previous_animation = self.animation_name()
        self.previous_frame = self.animation_frame(self.previous_animation)
        self.transition_timer = HOLLOW_TRANSITION_DURATION
        self.state = state
        if reset_timer:
            self.timer = 0.0
        if state != "attack":
            self.hit_done = False

    def hurt_box(self):
        if self.state == "dead":
            return pygame.Rect(int(self.pos.x - 48), int(self.pos.y - 30), 96, 30)
        return pygame.Rect(int(self.pos.x - 22), int(self.pos.y - 108), 44, 108)

    def attack_box(self):
        # Only frames 5–7 of the ten-frame strip carry a damaging blade.
        if self.state == "attack" and 5 <= self.animation_frame("attack") <= 7:
            left = self.pos.x + 18 if self.facing > 0 else self.pos.x - 88
            return pygame.Rect(int(left), int(self.pos.y - 91), 70, 76)
        return None

    def receive(self, damage, direction):
        if self.state == "dead":
            return False
        self.hp = max(0, self.hp - damage)
        self.flash = .16
        self.health_bar_timer = HOLLOW_HEALTH_BAR_TIME
        self.facing = -direction
        self.set_state("dead" if not self.hp else "hurt")
        return True

    def parried(self):
        self.set_state("stagger")
        self.hit_done = True
        self.health_bar_timer = HOLLOW_HEALTH_BAR_TIME

    @property
    def health_ratio(self):
        return clamp(self.hp / self.max_hp, 0, 1)

    def health_bar_visible(self):
        return self.state != "dead" and (
            self.health_bar_timer > 0
            or self.state in ("chase", "attack", "hurt", "stagger")
        )

    def update(self, dt, hero, neighbors):
        self.timer += dt
        self.transition_timer = max(0, self.transition_timer - dt)
        self.flash = max(0, self.flash - dt)
        self.health_bar_timer = max(0, self.health_bar_timer - dt)
        self.attack_cooldown = max(0, self.attack_cooldown - dt)
        if self.state == "dead":
            return None
        distance = hero.pos.x - self.pos.x
        absolute = abs(distance)
        target_facing = 1 if distance > 0 else -1
        if self.state == "hurt":
            if self.timer >= HOLLOW_HURT_DURATION:
                self.set_state("chase" if absolute < HOLLOW_LOSE_RANGE and hero.hp else "patrol")
            return None
        if self.state == "stagger":
            if self.timer >= HOLLOW_STAGGER_DURATION:
                self.set_state("chase" if absolute < HOLLOW_LOSE_RANGE and hero.hp else "patrol")
            return None
        if self.state == "attack":
            box = self.attack_box()
            if box and not self.hit_done and box.colliderect(hero.hurt_box()):
                self.hit_done = True
                if hero.parry_active():
                    self.parried()
                    return "parry"
                return hero.take_damage(self.damage, self.facing, self.pos.x)
            if self.timer >= HOLLOW_ATTACK_DURATION:
                self.attack_cooldown = .86 if self.strong else .68
                self.set_state("chase" if hero.hp else "patrol")
            return None

        if not hero.hp and self.state == "chase":
            self.set_state("patrol")
        elif hero.hp and absolute <= HOLLOW_VISION_RANGE and self.state in ("idle", "patrol"):
            self.set_state("chase")

        if self.state == "idle":
            if self.timer >= self.idle_duration:
                self.idle_duration = random.uniform(.55, 1.15)
                self.set_state("patrol")
            return None

        if self.state == "chase":
            beyond_leash = abs(self.pos.x - self.spawn_x) >= HOLLOW_LEASH_RANGE
            if absolute > HOLLOW_LOSE_RANGE or (beyond_leash and target_facing == self.patrol_direction):
                self.patrol_direction = -1 if self.pos.x > self.spawn_x else 1
                self.set_state("patrol")
                return None
            self.facing = target_facing
            if absolute <= HOLLOW_ATTACK_RANGE and self.attack_cooldown <= 0:
                self.set_state("attack")
                self.hit_done = False
            else:
                blocked = any(other is not self and other.state != "dead" and abs(other.pos.x - self.pos.x) < 54 and (other.pos.x - self.pos.x) * self.facing > 0 for other in neighbors)
                if not blocked:
                    self.pos.x += self.facing * (74 if self.strong else 92) * dt
        elif self.state == "patrol":
            distance_from_post = self.pos.x - self.spawn_x
            if abs(distance_from_post) > 96:
                self.patrol_direction = -1 if self.pos.x > self.spawn_x else 1
            self.facing = self.patrol_direction
            return_speed = 48 if abs(distance_from_post) > 120 else 24
            self.pos.x += self.patrol_direction * return_speed * dt
            if abs(distance_from_post) < 8 and self.timer > 2.2:
                self.set_state("idle")
        self.pos.x = clamp(self.pos.x, self.spawn_x - HOLLOW_LEASH_RANGE, self.spawn_x + HOLLOW_LEASH_RANGE)
        return None

    def draw(self, surface, sprites, offset):
        if not sprites or (self.state == "dead" and self.timer > 1.2):
            return
        name = self.animation_name()
        frame = sprites[name][self.animation_frame(name)]
        if self.facing < 0:
            frame = pygame.transform.flip(frame, True, False)
        if self.flash:
            frame = frame.copy()
            frame.fill((85, 25, 20, 0), special_flags=pygame.BLEND_RGB_ADD)
        pos = self.pos + offset
        pygame.draw.ellipse(surface, (5, 6, 8), (pos.x - 35, GROUND + offset.y, 70, 11))
        if self.transition_timer and self.previous_animation in sprites:
            blend = self.transition_timer / HOLLOW_TRANSITION_DURATION
            previous = sprites[self.previous_animation][self.previous_frame].copy()
            if self.facing < 0:
                previous = pygame.transform.flip(previous, True, False)
            previous.set_alpha(int(255 * blend))
            surface.blit(previous, previous.get_rect(midbottom=(pos.x, pos.y + 2)))
            frame = frame.copy()
            frame.set_alpha(int(255 * (1 - blend)))
        surface.blit(frame, frame.get_rect(midbottom=(pos.x, pos.y + 2)))
        if self.health_bar_visible():
            width, height = 58, 6
            bar = pygame.Rect(round(pos.x - width / 2), round(pos.y - 132), width, height)
            pygame.draw.rect(surface, (5, 5, 7), bar.inflate(4, 4))
            pygame.draw.rect(surface, (39, 30, 30), bar)
            fill = bar.copy()
            fill.width = round(width * self.health_ratio)
            if fill.width:
                pygame.draw.rect(surface, (157, 92, 35) if self.strong else (139, 31, 37), fill)
                pygame.draw.line(surface, (220, 171, 85) if self.strong else (191, 68, 67), fill.topleft, fill.topright)
            pygame.draw.rect(surface, (119, 105, 88), bar, 1)


class Gundyr:
    def __init__(self):
        self.pos = pygame.Vector2(930, GROUND)
        self.velocity = pygame.Vector2()
        self.facing = -1
        self.hp = self.max_hp = 720.0
        self.state, self.timer = "intro", 0.0
        self.cooldown, self.phase = 1.0, 1
        self.hit_done = False
        self.combo_left = 0
        self.last_attack = ""
        self.flash = self.stagger = self.dead_time = 0.0
        self.moving = False

    def receive(self, damage):
        if self.state in ("intro", "dead"):
            return False
        self.hp = max(0, self.hp - damage)
        self.flash = .12
        if self.hp <= 0:
            self.state, self.timer = "dead", 0
        return True

    def parried(self):
        self.state, self.timer, self.stagger = "stagger", 0, 1.15
        self.velocity.x = -self.facing * 180
        self.hp = max(0, self.hp - 18)

    def select_attack(self, distance):
        if distance > 330:
            choices = ["charge", "leap", "thrust", "shoulder_thrust", "backstep"]
        elif distance > 150:
            choices = ["thrust", "shoulder_thrust", "sweep", "reverse_sweep", "delayed_slam", "leap", "backstep"]
        else:
            choices = ["sweep", "reverse_sweep", "slam", "combo", "backstep"]
        if self.phase == 2:
            choices += ["frenzy", "shockwave", "double_thrust"]
        choices = [choice for choice in choices if choice != self.last_attack] or choices
        self.state = random.choice(choices)
        self.last_attack, self.timer, self.hit_done = self.state, 0, False
        self.combo_left = 3 if self.state == "frenzy" else 2

    def finish(self, cooldown=.9):
        self.state, self.timer, self.hit_done = "idle", 0, False
        self.cooldown = cooldown * (1 if self.phase == 1 else .82)

    def strike(self, hero, reach, damage, parryable=True):
        # Damage is allowed only when the same red debug hitbox shown on
        # screen actually overlaps the player's blue hurtbox.
        attack_hitbox = self.attack_box()
        if self.hit_done or attack_hitbox is None:
            return None
        if not attack_hitbox.colliderect(hero.hurt_box()):
            return None
        self.hit_done = True
        if parryable and hero.parry_active():
            self.parried()
            return "parry"
        return hero.take_damage(damage, self.facing, self.pos.x)

    def hurt_box(self):
        return pygame.Rect(int(self.pos.x - 52), int(self.pos.y - 155), 104, 155)

    def attack_box(self):
        state, timer = self.state, self.timer
        reach = height = 0
        if state in ("sweep", "reverse_sweep"):
            active = .86 if state == "reverse_sweep" else .72
            if active < timer < active + .21:
                reach, height = (178 if state == "reverse_sweep" else 188), 130
        elif state in ("thrust", "shoulder_thrust"):
            active = .78 if state == "shoulder_thrust" else .66
            if active < timer < active + .3:
                reach, height = (152 if state == "shoulder_thrust" else 135), 112
        elif state == "charge" and .82 < timer < 1.45:
            reach, height = 108, 145
        elif state in ("combo", "frenzy", "double_thrust"):
            active = .38 if state == "frenzy" else (.45 if state == "double_thrust" else .48)
            if active < timer < active + .14:
                reach, height = (145 if state == "double_thrust" else 170), 125
        elif state in ("slam", "delayed_slam", "leap", "shockwave"):
            impact = 1.2 if state == "delayed_slam" else (1.05 if state == "shockwave" else .92)
            if impact < timer < impact + .17:
                if state == "shockwave":
                    return pygame.Rect(int(self.pos.x - 230), int(self.pos.y - 72), 460, 72)
                reach, height = 130, 132
        elif state == "transform" and .56 < timer < .8:
            return pygame.Rect(int(self.pos.x - 165), int(self.pos.y - 140), 330, 140)
        if not reach:
            return None
        left = self.pos.x if self.facing > 0 else self.pos.x - reach
        return pygame.Rect(int(left), int(self.pos.y - height), reach, height)

    def update(self, dt, hero):
        events = []
        self.moving = False
        self.timer += dt
        self.flash = max(0, self.flash - dt)
        distance = abs(hero.pos.x - self.pos.x)
        target_facing = 1 if hero.pos.x > self.pos.x else -1
        if self.state == "dead":
            self.dead_time += dt
            return events
        if self.state == "intro":
            if self.timer > 1.3:
                self.finish(1.1)
            return events
        if self.phase == 1 and self.hp <= self.max_hp / 2:
            self.phase, self.state, self.timer, self.hit_done = 2, "transform", 0, False
            return [("phase", self.pos.copy())]
        if self.state == "transform":
            if .56 < self.timer < .8 and not self.hit_done:
                self.hit_done = True
                if distance < 165:
                    result = hero.take_damage(18, target_facing, self.pos.x)
                    if result:
                        events.append((result, hero.pos.copy()))
                events.append(("shockwave", self.pos.copy()))
            if self.timer > 1.55:
                self.finish(1.0)
            return events
        if self.state == "stagger":
            self.velocity.x *= .9
            self.pos.x += self.velocity.x * dt
            if self.timer > self.stagger:
                self.finish(1.15)
            return events

        if self.state == "idle":
            self.facing = target_facing
            self.cooldown -= dt
            if distance > 200:
                self.pos.x += self.facing * (78 + self.phase * 12) * dt
                self.moving = True
            elif distance < 105:
                self.pos.x -= self.facing * 44 * dt
                self.moving = True
            # At long range Gundyr closes the gap instead of swinging at air.
            if self.cooldown <= 0 and distance <= 300:
                self.select_attack(distance)
        elif self.state == "backstep":
            if self.timer < .48:
                self.pos.x -= self.facing * 175 * dt
            if self.timer > .72:
                self.finish(.7)
        elif self.state in ("sweep", "reverse_sweep"):
            active = .86 if self.state == "reverse_sweep" else .72
            reach = 178 if self.state == "reverse_sweep" else 188
            damage = (26 if self.state == "reverse_sweep" else 24) + self.phase * 2
            if active < self.timer < active + .21:
                result = self.strike(hero, reach, damage)
                if result:
                    events.append((result, hero.pos.copy()))
            if self.timer > (1.5 if self.state == "reverse_sweep" else 1.38):
                self.finish(1.0)
        elif self.state in ("thrust", "shoulder_thrust"):
            active = .78 if self.state == "shoulder_thrust" else .66
            speed = 285 if self.state == "shoulder_thrust" else 245
            reach = 152 if self.state == "shoulder_thrust" else 135
            damage = 31 if self.state == "shoulder_thrust" else 28
            if active < self.timer < active + .3:
                self.pos.x += self.facing * speed * dt
                result = self.strike(hero, reach, damage)
                if result:
                    events.append((result, hero.pos.copy()))
            if self.timer > (1.55 if self.state == "shoulder_thrust" else 1.4):
                self.finish(1.0)
        elif self.state == "charge":
            if .82 < self.timer < 1.45:
                self.pos.x += self.facing * 330 * dt
                result = self.strike(hero, 108, 30)
                if result:
                    events.append((result, hero.pos.copy()))
            if self.timer > 1.82:
                self.finish(1.15)
        elif self.state in ("slam", "delayed_slam", "leap", "shockwave"):
            impact_time = 1.2 if self.state == "delayed_slam" else (1.05 if self.state == "shockwave" else .92)
            if self.state == "leap" and .68 < self.timer < 1.02:
                self.pos.x += self.facing * 290 * dt
            if impact_time < self.timer < impact_time + .17 and not self.hit_done:
                reach = 230 if self.state == "shockwave" else 130
                result = self.strike(hero, reach, 27 if self.state == "shockwave" else 33, False)
                self.hit_done = True
                events.append(("shockwave" if self.state == "shockwave" else "impact", self.pos.copy()))
                if result:
                    events.append((result, hero.pos.copy()))
            if self.timer > impact_time + .68:
                self.finish(1.05)
        elif self.state in ("combo", "frenzy", "double_thrust"):
            duration = .68 if self.state == "frenzy" else (.78 if self.state == "double_thrust" else .82)
            active = .38 if self.state == "frenzy" else (.45 if self.state == "double_thrust" else .48)
            if active < self.timer < active + .14:
                reach = 145 if self.state == "double_thrust" else 170
                damage = 18 if self.state in ("frenzy", "double_thrust") else 21
                result = self.strike(hero, reach, damage)
                if result:
                    events.append((result, hero.pos.copy()))
            if self.timer > duration:
                self.combo_left -= 1
                if self.combo_left and self.state != "stagger":
                    self.timer, self.hit_done, self.facing = 0, False, target_facing
                    self.pos.x += self.facing * 18
                elif self.state != "stagger":
                    self.finish(1.15)
        arena_origin = BOSS_ARENA_LEFT if self.pos.x >= BOSS_ARENA_LEFT else 0
        self.pos.x = clamp(self.pos.x, arena_origin + LEFT_WALL + 65, arena_origin + RIGHT_WALL - 65)
        return events

    def draw(self, surface, sprites, offset):
        if self.state == "dead" and self.dead_time > BOSS_DEATH_DURATION:
            return
        telegraph = {
            "sweep": .72, "reverse_sweep": .86,
            "thrust": .66, "shoulder_thrust": .78,
            "charge": .82, "slam": .92,
            "delayed_slam": 1.2, "leap": .92, "shockwave": 1.05,
            "combo": .48, "frenzy": .38, "double_thrust": .45,
        }
        pos = self.pos + offset
        if self.state in telegraph and self.timer < telegraph[self.state]:
            pygame.draw.line(surface, (164, 39, 37), (pos.x, pos.y - 142), (pos.x + self.facing * 115, pos.y - 52), 3)
        if self.phase == 2:
            aura = pygame.Surface((260, 230), pygame.SRCALPHA)
            pygame.draw.ellipse(aura, (121, 14, 28, 25), (10, 5, 240, 220))
            surface.blit(aura, (pos.x - 130, pos.y - 202))
        shadow = pygame.Rect(0, 0, 124, 16)
        shadow.center = pos.x, GROUND + 9 + offset.y
        pygame.draw.ellipse(surface, (4, 4, 5), shadow)
        if self.state == "dead":
            name, duration = "slam", 1.0
        elif self.state == "sweep":
            name, duration = "sweep_a", 1.38
        elif self.state in ("reverse_sweep", "combo", "frenzy"):
            name = "sweep_b"
            duration = .68 if self.state == "frenzy" else (1.5 if self.state == "reverse_sweep" else .82)
        elif self.state == "thrust":
            name, duration = "thrust_a", 1.4
        elif self.state in ("shoulder_thrust", "double_thrust", "charge"):
            name = "thrust_b"
            duration = 1.55 if self.state == "shoulder_thrust" else (1.82 if self.state == "charge" else .78)
        elif self.state in ("slam", "delayed_slam", "shockwave"):
            name, duration = "slam", (1.88 if self.state == "delayed_slam" else 1.72)
        elif self.state in ("leap", "backstep", "transform"):
            name, duration = "special", 1.6
        elif self.state == "idle":
            name, duration = ("walk" if self.moving else "idle"), .9
        else:
            name, duration = "idle", 1.0
        frames = sprites[name]
        if self.state == "dead":
            # Skip the weapon-raising frames and move directly from standing
            # into the low, halberd-braced kneeling poses.
            death_sequence = (0, 5, 6, 7)
            kneel = clamp(self.dead_time / .72, 0, 1)
            frame_index = death_sequence[min(len(death_sequence) - 1, int(kneel * len(death_sequence)))]
        elif name in ("idle", "walk"):
            speed = 9 if name == "walk" else 4
            frame_index = int(self.timer * speed) % len(frames)
        else:
            frame_index = min(len(frames) - 1, int(self.timer / duration * len(frames)))
        frame = frames[frame_index]
        # The generated source frames face right.
        if self.facing < 0:
            frame = pygame.transform.flip(frame, True, False)
        if self.flash:
            frame = frame.copy()
            frame.fill((90, 30, 24, 0), special_flags=pygame.BLEND_RGB_ADD)
        death_sink = 0
        if self.state == "dead":
            kneel = kneel * kneel * (3 - 2 * kneel)
            death_sink = int(5 * kneel)
            fade = 1 - clamp((self.dead_time - 1.05) / (BOSS_DEATH_DURATION - 1.05), 0, 1)
            frame = frame.copy()
            frame.fill((150, 137, 126, 255), special_flags=pygame.BLEND_RGBA_MULT)
            frame.set_alpha(int(255 * fade))
        # The scaled strips retain three transparent pixels below the boots.
        # Four pixels place the visible soles one pixel into the shadow/ground.
        rect = frame.get_rect(midbottom=(pos.x, pos.y + 4 + death_sink))
        surface.blit(frame, rect)
        if self.state == "stagger":
            draw_text(surface, pygame.font.SysFont("georgia", 18), "VULNERÁVEL", (pos.x, pos.y - 175), (226, 182, 87), "center")


class Game:
    CHEAT_HEALTH_OPTIONS = (50, 110, 250, 500, 1000, 9999)
    CHEAT_DAMAGE_OPTIONS = (.5, 1.0, 2.0, 5.0, 10.0, 50.0)

    def __init__(self, capture=False):
        pygame.init()
        pygame.display.set_caption("Dark Souls 2D")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.font_small = pygame.font.SysFont("georgia", 17)
        self.font_ui = pygame.font.SysFont("georgia", 23)
        self.font_large = pygame.font.SysFont("georgia", 62)
        self.font_death = pygame.font.SysFont("georgia", 82)
        menu_font_path = pygame.font.match_font(("garamond", "perpetua", "georgia", "timesnewroman"))
        self.font_menu_title = pygame.font.Font(menu_font_path, 106)
        self.font_menu_title.set_bold(True)
        self.font_menu_heading = pygame.font.Font(menu_font_path, 48)
        self.font_menu_heading.set_bold(True)
        self.font_menu_option = pygame.font.Font(menu_font_path, 27)
        self.menu_play_button = pygame.Rect(WIDTH // 2 - 130, 428, 260, 48)
        self.menu_cheats_button = pygame.Rect(WIDTH // 2 - 130, 482, 260, 48)
        self.pause_continue_button = pygame.Rect(WIDTH // 2 - 155, 365, 310, 48)
        self.pause_menu_button = pygame.Rect(WIDTH // 2 - 155, 423, 310, 48)
        self.cheat_arrow_rects = {
            "health_down": pygame.Rect(WIDTH // 2 - 100, 343, 48, 42),
            "health_up": pygame.Rect(WIDTH // 2 + 96, 343, 48, 42),
            "damage_down": pygame.Rect(WIDTH // 2 - 100, 413, 48, 42),
            "damage_up": pygame.Rect(WIDTH // 2 + 96, 413, 48, 42),
        }
        self.cheat_back_button = pygame.Rect(WIDTH // 2 - 110, 505, 220, 46)
        self.menu_title = self.font_menu_title.render("DARK SOULS 2D", True, (224, 223, 216)).convert_alpha()
        # Break the otherwise pristine system font into a restrained, worn logo.
        weathering = random.Random(2016)
        for _ in range(54):
            scratch = pygame.Rect(
                weathering.randrange(self.menu_title.get_width()),
                weathering.randrange(self.menu_title.get_height()),
                weathering.randrange(2, 10),
                weathering.choice((1, 1, 2)),
            )
            self.menu_title.fill((70, 70, 70, 255), scratch, special_flags=pygame.BLEND_RGBA_MULT)
        self.art = SpriteArt()
        self.background = self.build_background()
        self.death_vignette = self.build_death_vignette()
        self.capture = capture
        self.show_hitboxes = False
        self.menu = True
        self.menu_page = "main"
        self.menu_selection = 0
        self.pause_selection = 0
        self.cheat_selection = 0
        self.cheat_health_index = self.CHEAT_HEALTH_OPTIONS.index(110)
        self.cheat_damage_index = self.CHEAT_DAMAGE_OPTIONS.index(1.0)
        self.music_ready = False
        self.world = World()
        self.bonfire = Bonfire()
        self.fog_gate = FogGate()
        self.souls = 0
        self.restart()

    def start_music(self):
        """Start the boss theme when an audio device and OST file are available."""
        track = ROOT / "ost" / "Iudex Gundyr (Vorbis).ogg"
        try:
            if track.exists():
                pygame.mixer.music.load(track)
                pygame.mixer.music.set_volume(.42)
                pygame.mixer.music.play(-1, fade_ms=1200)
                self.music_ready = True
        except pygame.error:
            # Headless preview/tests and machines without an audio device still run.
            self.music_ready = False

    def restart(self):
        self.hero = Hero(
            self.CHEAT_HEALTH_OPTIONS[self.cheat_health_index],
            self.CHEAT_DAMAGE_OPTIONS[self.cheat_damage_index],
        )
        self.hero.pos.x = BONFIRE_X + 95
        self.boss = Gundyr()
        self.boss.pos.x = BOSS_SPAWN_X
        self.hollows = [Hollow(x, index == len(HOLLOW_SPAWNS) - 1) for index, x in enumerate(HOLLOW_SPAWNS)]
        self.area = "explore"
        self.camera_x = 0.0
        self.world_time = 0.0
        self.fog_transition = 0.0
        if hasattr(self, "fog_gate"):
            self.fog_gate.reset()
        else:
            self.fog_gate = FogGate()
        self.boss_defeated = False
        if not hasattr(self, "souls"):
            self.souls = 0
        self.particles, self.waves = [], []
        self.shake = self.freeze = self.end_timer = 0.0
        self.help_time, self.paused = 8.0, False

    def respawn_at_bonfire(self):
        """Return the player to the last bonfire and restore the route."""
        if self.music_ready:
            pygame.mixer.music.fadeout(500)
            self.music_ready = False
        self.hero = Hero(
            self.CHEAT_HEALTH_OPTIONS[self.cheat_health_index],
            self.CHEAT_DAMAGE_OPTIONS[self.cheat_damage_index],
        )
        self.hero.pos.x = BONFIRE_X + 95
        self.hollows = [Hollow(x, index == len(HOLLOW_SPAWNS) - 1) for index, x in enumerate(HOLLOW_SPAWNS)]
        self.area, self.camera_x = "explore", 0.0
        self.fog_transition = self.end_timer = self.freeze = self.shake = 0.0
        self.fog_gate.reset()
        self.particles, self.waves = [], []

    def rest_at_bonfire(self):
        self.hero.hp = self.hero.max_hp
        self.hero.stamina = self.hero.max_stamina
        self.hero.flasks = 3
        self.hollows = [Hollow(x, index == len(HOLLOW_SPAWNS) - 1) for index, x in enumerate(HOLLOW_SPAWNS)]
        self.burst(pygame.Vector2(BONFIRE_X, GROUND - 35), (235, 139, 43), 34, 145)

    def begin_fog_transition(self):
        if (
            self.area == "explore"
            and not self.boss_defeated
            and not self.fog_transition
            and self.fog_gate.begin(self.hero)
        ):
            self.fog_transition = FOG_ENTER_DURATION

    def enter_boss_arena(self):
        self.area = "boss"
        self.camera_x = float(BOSS_ARENA_LEFT)
        self.hero.pos.xy = BOSS_ARENA_LEFT + 190, GROUND
        self.hero.velocity.xy = 0, 0
        self.boss = Gundyr()
        self.boss.pos.x = BOSS_SPAWN_X
        self.fog_transition = self.end_timer = 0.0
        self.particles, self.waves = [], []
        self.start_music()

    def return_after_victory(self):
        self.area = "explore"
        self.hero.pos.xy = FOG_GATE_X - 145, GROUND
        self.hero.hp = max(1, self.hero.hp)
        self.hero.state, self.hero.timer = "idle", 0.0
        self.camera_x = clamp(self.hero.pos.x - WIDTH * .42, 0, WORLD_WIDTH - WIDTH)
        self.end_timer = self.freeze = self.shake = 0.0
        self.particles, self.waves = [], []

    def build_background(self):
        arena_path = ROOT / "assets" / "arena_gundyr_v1.png"
        if arena_path.exists():
            arena = pygame.image.load(arena_path).convert()
            arena = pygame.transform.smoothscale(arena, (WIDTH, HEIGHT))
            # Pull the detailed painting into the same restrained value range
            # as the actors and UI while keeping the cold sky readable.
            arena.fill((176, 181, 191), special_flags=pygame.BLEND_RGB_MULT)
            cold_grade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            cold_grade.fill((15, 22, 31, 38))
            arena.blit(cold_grade, (0, 0))
            return arena

        surface = pygame.Surface((WIDTH, HEIGHT))
        surface.fill((12, 10, 14))
        pygame.draw.circle(surface, (107, 21, 28), (WIDTH // 2, 195), 128)
        pygame.draw.circle(surface, (23, 17, 22), (WIDTH // 2 + 35, 175), 109)
        for x in range(65, WIDTH, 190):
            pygame.draw.rect(surface, (25, 23, 28), (x, 75, 40, GROUND - 70))
            pygame.draw.polygon(surface, (37, 33, 37), [(x - 26, 142), (x + 20, 73), (x + 66, 142)])
            pygame.draw.line(surface, (54, 46, 47), (x + 20, 82), (x + 20, GROUND), 3)
        for x in range(145, WIDTH, 250):
            pygame.draw.arc(surface, (48, 40, 43), (x, 160, 170, 300), math.pi, math.tau, 8)
            pygame.draw.line(surface, (39, 34, 38), (x, 310), (x, GROUND), 8)
            pygame.draw.line(surface, (39, 34, 38), (x + 170, 310), (x + 170, GROUND), 8)
        random.seed(41)
        for _ in range(34):
            x = random.randint(80, WIDTH - 80)
            height = random.randint(25, 85)
            pygame.draw.rect(surface, (31, 29, 32), (x, GROUND - height, random.randint(12, 30), height))
            pygame.draw.polygon(surface, (41, 37, 39), [(x - 5, GROUND-height), (x + 10, GROUND-height-18), (x + 25, GROUND-height)])
        pygame.draw.rect(surface, (47, 42, 41), (0, GROUND, WIDTH, HEIGHT - GROUND))
        pygame.draw.line(surface, (105, 82, 66), (0, GROUND), (WIDTH, GROUND), 4)
        for x in range(0, WIDTH, 72):
            pygame.draw.line(surface, (32, 29, 31), (x, GROUND + 5), (x - 24, HEIGHT), 3)
        fog = pygame.Surface((WIDTH, 140), pygame.SRCALPHA)
        for _ in range(14):
            pygame.draw.ellipse(fog, (115, 106, 103, 9), (random.randint(-80, WIDTH), random.randint(0, 100), random.randint(130, 300), 45))
        surface.blit(fog, (0, GROUND - 85))
        return surface

    @staticmethod
    def build_death_vignette():
        vignette = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        for layer in range(14):
            inset_x = layer * 18
            inset_y = layer * 10
            alpha = max(8, 54 - layer * 3)
            pygame.draw.rect(
                vignette,
                (0, 0, 0, alpha),
                (inset_x, inset_y, WIDTH - inset_x * 2, HEIGHT - inset_y * 2),
                24,
            )
        return vignette

    @staticmethod
    def movement():
        keys = pygame.key.get_pressed()
        return keys[pygame.K_d] - keys[pygame.K_a]

    def burst(self, pos, color, count=18, speed=210):
        for _ in range(count):
            velocity = pygame.Vector2(random.uniform(-1, 1), random.uniform(-1.2, -.1)).normalize() * random.uniform(speed * .3, speed)
            self.particles.append(Particle(pos.copy(), velocity, color, random.uniform(.25, .65), random.uniform(2, 6), 520))

    def activate_menu_selection(self):
        if self.menu_selection == 0:
            self.menu = False
            self.restart()
        else:
            self.menu_page = "cheats"
            self.cheat_selection = 0

    def adjust_cheat(self, direction):
        if self.cheat_selection == 0:
            self.cheat_health_index = int(clamp(
                self.cheat_health_index + direction,
                0,
                len(self.CHEAT_HEALTH_OPTIONS) - 1,
            ))
        else:
            self.cheat_damage_index = int(clamp(
                self.cheat_damage_index + direction,
                0,
                len(self.CHEAT_DAMAGE_OPTIONS) - 1,
            ))

    def reset_cheats(self):
        self.cheat_health_index = self.CHEAT_HEALTH_OPTIONS.index(110)
        self.cheat_damage_index = self.CHEAT_DAMAGE_OPTIONS.index(1.0)

    def return_to_main_menu(self):
        if self.music_ready:
            pygame.mixer.music.fadeout(600)
            self.music_ready = False
        self.menu = True
        self.menu_page = "main"
        self.menu_selection = 0
        self.paused = False
        self.restart()

    def activate_pause_selection(self):
        if self.pause_selection == 0:
            self.paused = False
        else:
            self.return_to_main_menu()

    def handle_events(self):
        jump = False
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False, jump
            if event.type == pygame.KEYDOWN:
                if self.menu:
                    if self.menu_page == "main":
                        if event.key in (pygame.K_UP, pygame.K_w):
                            self.menu_selection = (self.menu_selection - 1) % 2
                        elif event.key in (pygame.K_DOWN, pygame.K_s):
                            self.menu_selection = (self.menu_selection + 1) % 2
                        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                            self.activate_menu_selection()
                        elif event.key == pygame.K_ESCAPE:
                            return False, jump
                    else:
                        if event.key in (pygame.K_UP, pygame.K_w, pygame.K_DOWN, pygame.K_s):
                            self.cheat_selection = 1 - self.cheat_selection
                        elif event.key in (pygame.K_LEFT, pygame.K_a):
                            self.adjust_cheat(-1)
                        elif event.key in (pygame.K_RIGHT, pygame.K_d, pygame.K_RETURN, pygame.K_KP_ENTER):
                            self.adjust_cheat(1)
                        elif event.key == pygame.K_r:
                            self.reset_cheats()
                        elif event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                            self.menu_page = "main"
                    continue
                if self.paused:
                    if event.key == pygame.K_ESCAPE:
                        self.paused = False
                    elif event.key in (pygame.K_UP, pygame.K_w):
                        self.pause_selection = (self.pause_selection - 1) % 2
                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        self.pause_selection = (self.pause_selection + 1) % 2
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                        self.activate_pause_selection()
                    continue
                if event.key == pygame.K_ESCAPE:
                    self.paused = True
                    self.pause_selection = 0
                elif event.key == pygame.K_F3:
                    self.show_hitboxes = not self.show_hitboxes
                elif event.key == pygame.K_h:
                    self.help_time = 999 if self.help_time < 20 else 0
                elif event.key == pygame.K_r and not self.hero.hp:
                    self.respawn_at_bonfire()
                elif event.key == pygame.K_r and self.area == "boss" and not self.boss.hp:
                    self.return_after_victory()
                elif not self.paused and self.hero.hp and (self.area != "boss" or self.boss.hp):
                    if event.key in (pygame.K_w, pygame.K_UP):
                        jump = True
                    elif event.key in (pygame.K_SPACE, pygame.K_LSHIFT):
                        self.hero.dodge(self.movement())
                    elif event.key == pygame.K_q:
                        self.hero.parry()
                    elif event.key == pygame.K_e:
                        self.hero.heal()
                    elif event.key == pygame.K_g and self.area == "explore":
                        if self.bonfire.near(self.hero):
                            self.rest_at_bonfire()
                        elif self.fog_gate.near(self.hero):
                            self.begin_fog_transition()
            if event.type == pygame.MOUSEBUTTONDOWN and self.menu:
                if event.button == 1 and self.menu_page == "main":
                    if self.menu_play_button.collidepoint(event.pos):
                        self.menu_selection = 0
                        self.activate_menu_selection()
                    elif self.menu_cheats_button.collidepoint(event.pos):
                        self.menu_selection = 1
                        self.activate_menu_selection()
                elif event.button == 1:
                    if self.cheat_arrow_rects["health_down"].collidepoint(event.pos):
                        self.cheat_selection = 0
                        self.adjust_cheat(-1)
                    elif self.cheat_arrow_rects["health_up"].collidepoint(event.pos):
                        self.cheat_selection = 0
                        self.adjust_cheat(1)
                    elif self.cheat_arrow_rects["damage_down"].collidepoint(event.pos):
                        self.cheat_selection = 1
                        self.adjust_cheat(-1)
                    elif self.cheat_arrow_rects["damage_up"].collidepoint(event.pos):
                        self.cheat_selection = 1
                        self.adjust_cheat(1)
                    elif self.cheat_back_button.collidepoint(event.pos):
                        self.menu_page = "main"
                continue
            if event.type == pygame.MOUSEBUTTONDOWN and self.paused:
                if event.button == 1 and self.pause_continue_button.collidepoint(event.pos):
                    self.pause_selection = 0
                    self.activate_pause_selection()
                elif event.button == 1 and self.pause_menu_button.collidepoint(event.pos):
                    self.pause_selection = 1
                    self.activate_pause_selection()
                continue
            if event.type == pygame.MOUSEBUTTONDOWN and not self.paused and self.hero.hp and (self.area != "boss" or self.boss.hp):
                if event.button == 1:
                    self.hero.attack()
                elif event.button == 3:
                    self.hero.attack(True)
        return True, jump

    def update(self, dt, jump):
        if self.menu or self.paused:
            return
        self.world_time += dt
        self.help_time = max(0, self.help_time - dt)
        if self.freeze > 0:
            self.freeze = max(0, self.freeze - dt)
            return
        defending = pygame.key.get_pressed()[pygame.K_f]
        if self.area == "explore" and self.fog_gate.entering:
            # The gate owns horizontal movement during the short crossing.
            # Hero internals and animation assets remain untouched.
            self.hero.velocity.x = 0
        elif self.area == "explore":
            right_bound = WORLD_RIGHT if self.boss_defeated else FOG_GATE_X - 58
            self.hero.update(dt, self.movement(), jump, defending, WORLD_LEFT, right_bound)
        else:
            self.hero.update(
                dt,
                self.movement(),
                jump,
                defending,
                BOSS_ARENA_LEFT + LEFT_WALL,
                BOSS_ARENA_LEFT + RIGHT_WALL,
            )
        if self.hero.heal_effect:
            self.burst(
                self.hero.pos - pygame.Vector2(0, 54),
                (238, 147, 35),
                24,
                125,
            )

        if self.area == "explore":
            self.update_exploration(dt)
        else:
            self.fog_gate.advance(dt)
            self.update_boss(dt)

        self.particles = [particle for particle in self.particles if particle.update(dt)]
        for wave in self.waves:
            wave[1] += 360 * dt
            wave[2] -= dt
        self.waves = [wave for wave in self.waves if wave[2] > 0]
        self.shake = max(0, self.shake - 24 * dt)
        if not self.hero.hp or (self.area == "boss" and not self.boss.hp):
            self.end_timer += dt
            if self.music_ready:
                pygame.mixer.music.fadeout(1100)
                self.music_ready = False
        self.camera_x = (
            clamp(self.hero.pos.x - WIDTH * .42, 0, WORLD_WIDTH - WIDTH)
            if self.area == "explore"
            else float(BOSS_ARENA_LEFT)
        )

    def update_exploration(self, dt):
        crossed = self.fog_gate.update(dt, self.hero, not self.boss_defeated)
        if self.fog_gate.entering or crossed:
            self.fog_transition = max(0, FOG_ENTER_DURATION - self.fog_gate.elapsed)
            if crossed:
                self.enter_boss_arena()
            return

        for hollow in self.hollows:
            result = hollow.update(dt, self.hero, self.hollows)
            if result == "hit":
                self.shake, self.freeze = 8, .055
                self.burst(self.hero.pos - pygame.Vector2(0, 48), (147, 28, 34), 13)
            elif result == "block":
                self.shake, self.freeze = 4, .035
                self.burst(self.hero.pos + pygame.Vector2(self.hero.facing * 35, -58), (218, 191, 125), 9, 125)
            elif result == "parry":
                self.shake, self.freeze = 10, .09
                self.burst(hollow.pos - pygame.Vector2(hollow.facing * 30, 64), (226, 196, 112), 18, 220)

        hitbox, damage = self.hero.attack_box()
        if hitbox and not self.hero.hit_done:
            for hollow in self.hollows:
                if hollow.state != "dead" and hitbox.colliderect(hollow.hurt_box()):
                    self.hero.hit_done = True
                    if hollow.receive(damage, self.hero.facing):
                        self.freeze, self.shake = ((.07, 7) if damage > 20 else (.035, 4))
                        self.burst(hollow.pos - pygame.Vector2(self.hero.facing * 25, 62), (135, 39, 36), 12)
                        if hollow.state == "dead" and not hollow.rewarded:
                            hollow.rewarded = True
                            self.souls += HOLLOW_SOULS * (2 if hollow.strong else 1)
                            self.burst(hollow.pos - pygame.Vector2(0, 58), (139, 144, 151), 20, 135)
                    break

        for hollow in self.hollows:
            if hollow.state != "dead" and abs(self.hero.pos.x - hollow.pos.x) < 48 and self.hero.grounded and self.hero.state != "dodge":
                direction = 1 if self.hero.pos.x > hollow.pos.x else -1
                self.hero.pos.x += direction * (48 - abs(self.hero.pos.x - hollow.pos.x)) * .55

    def update_boss(self, dt):
        for kind, pos in self.boss.update(dt, self.hero):
            if kind == "hit":
                self.shake, self.freeze = 12, .075
                self.burst(pos - pygame.Vector2(0, 45), (147, 28, 34), 20)
            elif kind == "block":
                self.shake, self.freeze = 5, .045
                shield_pos = self.hero.pos + pygame.Vector2(self.hero.facing * 38, -62)
                self.burst(shield_pos, (218, 191, 125), 12, 150)
            elif kind == "parry":
                self.shake, self.freeze = 15, .14
                self.burst(self.boss.pos - pygame.Vector2(self.boss.facing * 62, 90), (226, 196, 112), 28, 300)
            elif kind == "phase":
                self.shake = 17
                self.burst(pos - pygame.Vector2(0, 70), (144, 19, 37), 55, 280)
            else:
                self.shake = 11
                self.waves.append([pos.copy(), 20.0, .65])
                self.burst(pos - pygame.Vector2(0, 8), (115, 90, 74), 30, 260)
        hitbox, damage = self.hero.attack_box()
        boss_box = self.boss.hurt_box()
        if hitbox and not self.hero.hit_done and hitbox.colliderect(boss_box):
            self.hero.hit_done = True
            boss_was_alive = self.boss.hp > 0
            if self.boss.receive(damage):
                self.freeze, self.shake = ((.09, 9) if damage > 20 else (.05, 5))
                self.burst(self.boss.pos - pygame.Vector2(self.hero.facing * 45, 85), (153, 37, 36), 15)
                if boss_was_alive and not self.boss.hp:
                    self.freeze, self.shake = .18, 20
                    self.waves.append([self.boss.pos.copy(), 25.0, .9])
                    self.burst(self.boss.pos - pygame.Vector2(0, 78), (202, 108, 43), 38, 280)
                    self.burst(self.boss.pos - pygame.Vector2(0, 55), (94, 86, 78), 46, 190)
                    self.boss_defeated = True
                    self.souls += 3000
        # During a dodge the hero can roll through the boss. Body separation
        # resumes as soon as the roll ends.
        if self.boss.hp and abs(self.hero.pos.x - self.boss.pos.x) < 72 and self.hero.grounded and self.hero.state != "dodge":
            direction = 1 if self.hero.pos.x > self.boss.pos.x else -1
            overlap = 72 - abs(self.hero.pos.x - self.boss.pos.x)
            self.hero.pos.x += direction * overlap * .72
            self.boss.pos.x -= direction * overlap * .28
        if self.boss.state == "dead" and self.boss.dead_time < BOSS_DEATH_DURATION:
            for _ in range(2):
                if random.random() < 18 * dt:
                    ash_pos = self.boss.pos + pygame.Vector2(random.uniform(-62, 62), random.uniform(-135, -18))
                    ash_velocity = pygame.Vector2(random.uniform(-28, 28), random.uniform(-95, -32))
                    ash_color = random.choice(((171, 91, 38), (112, 97, 82), (73, 69, 65)))
                    self.particles.append(Particle(ash_pos, ash_velocity, ash_color, random.uniform(.5, 1.1), random.uniform(2, 5), -12))

    def draw_bar(self, rect, ratio, color):
        pygame.draw.rect(self.screen, (3, 3, 5), rect.inflate(10, 8))
        pygame.draw.rect(self.screen, (27, 24, 27), rect)
        filled = rect.copy()
        filled.width = int(rect.width * clamp(ratio, 0, 1))
        if filled.width:
            pygame.draw.rect(self.screen, color, filled)
            pygame.draw.line(self.screen, tuple(min(255, c + 35) for c in color), filled.topleft, filled.topright, 2)
        pygame.draw.rect(self.screen, (105, 91, 79), rect, 1)

    def draw_hud(self):
        panel = pygame.Surface((430, 126), pygame.SRCALPHA)
        panel.fill((3, 3, 5, 198))
        self.screen.blit(panel, (18, 15))
        pygame.draw.circle(self.screen, (16, 15, 18), (62, 61), 39)
        pygame.draw.circle(self.screen, (151, 124, 73), (62, 61), 39, 3)
        pygame.draw.circle(self.screen, (83, 22, 27), (62, 61), 29)
        pygame.draw.polygon(self.screen, (185, 39, 43), [(62, 36), (74, 61), (62, 86), (50, 61)])
        self.draw_bar(pygame.Rect(112, 33, 310, 20), self.hero.hp / self.hero.max_hp, (154, 32, 39))
        self.draw_bar(pygame.Rect(112, 64, 272, 12), self.hero.stamina / self.hero.max_stamina, (57, 132, 74))
        pygame.draw.line(self.screen, (205, 180, 115), (112, 56), (422, 56), 1)
        icon_rect = self.art.estus_icon.get_rect(midleft=(112, 106))
        self.screen.blit(self.art.estus_icon, icon_rect)
        draw_text(
            self.screen,
            self.font_small,
            f"ESTUS   × {self.hero.flasks}",
            (157, 96),
            (222, 174, 80),
        )
        souls_panel = pygame.Surface((176, 42), pygame.SRCALPHA)
        souls_panel.fill((3, 3, 5, 188))
        self.screen.blit(souls_panel, (WIDTH - 194, 22))
        pygame.draw.circle(self.screen, (62, 70, 76), (WIDTH - 168, 43), 9)
        pygame.draw.circle(self.screen, (145, 151, 153), (WIDTH - 168, 43), 9, 1)
        draw_text(self.screen, self.font_ui, f"{self.souls:07d}", (WIDTH - 37, 43), (214, 210, 197), "midright")
        if self.area == "boss" and (self.boss.state != "intro" or self.boss.timer > .45):
            rect = pygame.Rect(205, HEIGHT - 69, WIDTH - 410, 18)
            self.draw_bar(rect, self.boss.hp / self.boss.max_hp, (128, 25, 33))
            draw_text(self.screen, self.font_ui, "IUDEX GUNDYR", (rect.left, rect.top - 35), (207, 194, 170))
            draw_text(self.screen, self.font_small, f"FASE {self.boss.phase}", (rect.right, rect.top - 29), (161, 149, 136), "topright")

    def draw_main_menu(self):
        self.screen.fill((1, 1, 2))

        # A nearly black field with a faint warm center keeps the logo readable
        # while retaining the austere Dark Souls menu composition.
        haze = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        for radius, alpha in ((430, 5), (310, 7), (205, 9)):
            pygame.draw.ellipse(
                haze,
                (90, 65, 34, alpha),
                (WIDTH // 2 - radius, 115, radius * 2, radius),
            )
        self.screen.blit(haze, (0, 0))

        if self.menu_page == "cheats":
            self.draw_cheat_menu()
            return

        pygame.draw.line(self.screen, (73, 68, 61), (48, 318), (WIDTH - 48, 318), 1)
        title_rect = self.menu_title.get_rect(center=(WIDTH // 2, 302))
        title_shadow = self.font_menu_title.render("DARK SOULS 2D", True, (0, 0, 0))
        self.screen.blit(title_shadow, title_shadow.get_rect(center=(WIDTH // 2 + 3, 306)))
        self.screen.blit(self.menu_title, title_rect)

        self.draw_menu_option(self.menu_play_button, "JOGAR", self.menu_selection == 0)
        self.draw_menu_option(self.menu_cheats_button, "CHEATS", self.menu_selection == 1)

    def draw_menu_option(self, rect, label, selected):
        highlighted = selected or rect.collidepoint(pygame.mouse.get_pos())
        glow = pygame.Surface((rect.width + 120, rect.height), pygame.SRCALPHA)
        pygame.draw.ellipse(
            glow,
            (135, 91, 24, 34 if highlighted else 10),
            glow.get_rect(),
        )
        self.screen.blit(glow, glow.get_rect(center=rect.center))
        draw_text(
            self.screen,
            self.font_menu_option,
            label,
            rect.center,
            (224, 192, 125) if highlighted else (151, 144, 132),
            "center",
        )

    def draw_cheat_menu(self):
        draw_text(
            self.screen,
            self.font_menu_heading,
            "CHEATS DE TESTE",
            (WIDTH // 2, 220),
            (218, 216, 207),
            "center",
        )
        pygame.draw.line(self.screen, (73, 68, 61), (340, 272), (WIDTH - 340, 272), 1)

        mouse_pos = pygame.mouse.get_pos()
        rows = (
            ("VIDA DO JOGADOR", str(self.CHEAT_HEALTH_OPTIONS[self.cheat_health_index]), 364),
            ("DANO DO JOGADOR", f"{self.CHEAT_DAMAGE_OPTIONS[self.cheat_damage_index]:g}×", 434),
        )
        for index, (label, value, y) in enumerate(rows):
            selected = self.cheat_selection == index
            if selected:
                row_glow = pygame.Surface((520, 48), pygame.SRCALPHA)
                pygame.draw.ellipse(row_glow, (121, 82, 27, 22), row_glow.get_rect())
                self.screen.blit(row_glow, row_glow.get_rect(center=(WIDTH // 2, y)))
            draw_text(
                self.screen,
                self.font_small,
                label,
                (WIDTH // 2 - 125, y),
                (202, 190, 169) if selected else (139, 134, 126),
                "midright",
            )
            draw_text(
                self.screen,
                self.font_menu_option,
                value,
                (WIDTH // 2 + 22, y),
                (225, 193, 126) if selected else (184, 171, 147),
                "center",
            )

        arrow_pairs = (
            (self.cheat_arrow_rects["health_down"], "‹"),
            (self.cheat_arrow_rects["health_up"], "›"),
            (self.cheat_arrow_rects["damage_down"], "‹"),
            (self.cheat_arrow_rects["damage_up"], "›"),
        )
        for rect, symbol in arrow_pairs:
            color = (226, 194, 128) if rect.collidepoint(mouse_pos) else (153, 145, 132)
            draw_text(self.screen, self.font_menu_option, symbol, rect.center, color, "center")

        self.draw_menu_option(self.cheat_back_button, "VOLTAR", False)
        draw_text(
            self.screen,
            self.font_small,
            "SETAS ou W/A/S/D para ajustar   •   R restaura o padrão",
            (WIDTH // 2, 590),
            (105, 101, 95),
            "center",
        )

    def overlay(self, title, subtitle, color):
        veil = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        veil.fill((5, 4, 7, 182))
        self.screen.blit(veil, (0, 0))
        draw_text(self.screen, self.font_large, title, (WIDTH // 2, HEIGHT // 2 - 18), color, "center")
        draw_text(self.screen, self.font_ui, subtitle, (WIDTH // 2, HEIGHT // 2 + 51), (193, 181, 168), "center")

    def draw_pause_menu(self):
        veil = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        veil.fill((1, 1, 3, 218))
        self.screen.blit(veil, (0, 0))
        draw_text(
            self.screen,
            self.font_menu_heading,
            "PAUSADO",
            (WIDTH // 2, 276),
            (218, 216, 207),
            "center",
        )
        pygame.draw.line(self.screen, (87, 76, 62), (390, 325), (WIDTH - 390, 325), 1)
        self.draw_menu_option(self.pause_continue_button, "CONTINUAR", self.pause_selection == 0)
        self.draw_menu_option(self.pause_menu_button, "VOLTAR AO MENU", self.pause_selection == 1)
        draw_text(
            self.screen,
            self.font_small,
            "SETAS ou W/S para escolher   •   ENTER para confirmar",
            (WIDTH // 2, 520),
            (113, 108, 101),
            "center",
        )

    def draw_death_screen(self):
        fade = clamp((self.end_timer - .12) / 1.35, 0, 1)
        fade = fade * fade * (3 - 2 * fade)

        veil = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        veil.fill((2, 2, 3, int(205 * fade)))
        self.screen.blit(veil, (0, 0))

        vignette = self.death_vignette.copy()
        vignette.set_alpha(int(255 * fade))
        self.screen.blit(vignette, (0, 0))

        text_fade = clamp((self.end_timer - .52) / 1.05, 0, 1)
        text_fade = text_fade * text_fade * (3 - 2 * text_fade)
        text_alpha = int(235 * text_fade)
        center_y = HEIGHT // 2 - 18

        rule = pygame.Surface((700, 2), pygame.SRCALPHA)
        pygame.draw.line(rule, (119, 34, 36, int(105 * text_fade)), (0, 1), (700, 1))
        self.screen.blit(rule, (WIDTH // 2 - 350, center_y + 57))

        shadow = self.font_death.render("VOCÊ MORREU", True, (5, 2, 3))
        shadow.set_alpha(text_alpha)
        self.screen.blit(shadow, shadow.get_rect(center=(WIDTH // 2 + 3, center_y + 4)))

        title = self.font_death.render("VOCÊ MORREU", True, (137, 31, 34))
        title.set_alpha(text_alpha)
        self.screen.blit(title, title.get_rect(center=(WIDTH // 2, center_y)))

        prompt_fade = clamp((self.end_timer - 1.75) / .7, 0, 1)
        if prompt_fade:
            prompt = self.font_small.render("R   RENASCER NA FOGUEIRA", True, (174, 166, 154))
            prompt.set_alpha(int(210 * prompt_fade))
            self.screen.blit(
                prompt,
                prompt.get_rect(center=(WIDTH // 2, center_y + 105)),
            )

    def draw_debug_hitboxes(self, offset):
        if not self.show_hitboxes:
            return
        layer = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        shift = (int(offset.x), int(offset.y))

        def box(rect, color):
            if rect is None:
                return
            moved = rect.move(shift)
            pygame.draw.rect(layer, (*color, 42), moved)
            pygame.draw.rect(layer, (*color, 235), moved, 2)

        box(self.hero.hurt_box(), (45, 145, 255))
        if self.area == "boss" and self.boss.hp:
            box(self.boss.hurt_box(), (255, 155, 45))
        elif self.area == "explore":
            for hollow in self.hollows:
                if hollow.state != "dead":
                    box(hollow.hurt_box(), (224, 142, 52))
                    box(hollow.attack_box(), (255, 45, 65))
        hero_attack, _ = self.hero.attack_box()
        box(hero_attack, (45, 235, 100))
        if self.area == "boss":
            box(self.boss.attack_box(), (255, 45, 65))
        self.screen.blit(layer, (0, 0))

        legend = pygame.Surface((198, 91), pygame.SRCALPHA)
        legend.fill((4, 4, 6, 190))
        items = (
            ("JOGADOR", (45, 145, 255)),
            (("GUNDYR" if self.area == "boss" else "HOLLOW"), (255, 155, 45)),
            ("ATAQUE SEU", (45, 235, 100)),
            ("ATAQUE CHEFE", (255, 45, 65)),
        )
        for index, (label, color) in enumerate(items):
            y = 8 + index * 20
            pygame.draw.rect(legend, color, (9, y + 3, 16, 10), 2)
            legend.blit(self.font_small.render(label, True, (210, 202, 190)), (32, y))
        self.screen.blit(legend, (WIDTH - 218, 181))

    def draw(self):
        if self.menu:
            self.draw_main_menu()
            pygame.display.flip()
            return
        shake_offset = pygame.Vector2()
        if self.shake:
            shake_offset.xy = random.uniform(-self.shake, self.shake), random.uniform(-self.shake, self.shake)
        offset = pygame.Vector2(-self.camera_x, 0) + shake_offset
        if self.area == "explore":
            self.world.draw(self.screen, self.camera_x - shake_offset.x, self.world_time)
            self.bonfire.draw(self.screen, offset, self.world_time)
            self.fog_gate.draw(self.screen, offset, self.world_time, not self.boss_defeated, foreground=False)
        else:
            self.screen.blit(self.background, shake_offset)
            # The fog seals the arena behind the player while Gundyr lives.
            if self.boss.hp:
                self.fog_gate.draw(
                    self.screen,
                    offset,
                    self.world_time,
                    sealed=True,
                    foreground=False,
                    world_x=BOSS_ARENA_LEFT + 65,
                )
        for center, radius, life in self.waves:
            pygame.draw.ellipse(self.screen, (145, 43, 39), (center.x - radius + offset.x, GROUND - radius * .14 + offset.y, radius * 2, radius * .28), 4)
        actors = [(self.hero.pos.x, self.hero, self.art.hero)]
        if self.area == "boss":
            actors.append((self.boss.pos.x, self.boss, self.art.gundyr))
        else:
            actors.extend((hollow.pos.x, hollow, self.art.hollow) for hollow in self.hollows)
        for _, actor, sprites in sorted(actors, key=lambda item: item[0]):
            actor.draw(self.screen, sprites, offset)
        for particle in self.particles:
            particle.draw(self.screen, offset)
        if self.area == "explore":
            self.fog_gate.draw(self.screen, offset, self.world_time, not self.boss_defeated, foreground=True)
        elif self.boss.hp:
            self.fog_gate.draw(
                self.screen,
                offset,
                self.world_time,
                sealed=True,
                foreground=True,
                world_x=BOSS_ARENA_LEFT + 65,
            )
        self.draw_debug_hitboxes(offset)
        self.draw_hud()
        if self.area == "explore" and self.hero.hp and not self.paused and not self.fog_gate.entering:
            prompt = None
            if self.bonfire.near(self.hero):
                prompt = "G   DESCANSAR NA FOGUEIRA"
            elif self.fog_gate.near(self.hero) and not self.boss_defeated:
                prompt = "PRESSIONE G PARA ENTRAR"
            if prompt:
                prompt_panel = pygame.Surface((440, 44), pygame.SRCALPHA)
                prompt_panel.fill((3, 3, 5, 205))
                self.screen.blit(prompt_panel, prompt_panel.get_rect(center=(WIDTH // 2, HEIGHT - 76)))
                draw_text(self.screen, self.font_ui, prompt, (WIDTH // 2, HEIGHT - 76), (218, 208, 188), "center")
        if self.fog_transition:
            self.fog_gate.draw_transition_overlay(self.screen)
        if self.help_time:
            box = pygame.Surface((670, 151), pygame.SRCALPHA)
            box.fill((5, 5, 7, 224))
            self.screen.blit(box, (WIDTH // 2 - 335, 18))
            pygame.draw.rect(self.screen, (117, 96, 75), (WIDTH // 2 - 335, 18, 670, 151), 1)
            draw_text(self.screen, self.font_ui, "CEMITÉRIO DAS CINZAS", (WIDTH // 2, 32), anchor="midtop")
            draw_text(self.screen, self.font_small, "A/D mover  •  W pular  •  ESPAÇO rolar  •  F defender à frente", (WIDTH // 2, 70), (192, 184, 174), "midtop")
            draw_text(self.screen, self.font_small, "ESQ atacar  •  DIR golpe forte  •  Q aparar  •  E curar  •  G interagir", (WIDTH // 2, 99), (192, 184, 174), "midtop")
            draw_text(self.screen, self.font_small, "Explore até a névoa  •  F3 hitboxes  •  H oculta ajuda", (WIDTH // 2, 127), (164, 154, 143), "midtop")
        if self.paused:
            self.draw_pause_menu()
        elif not self.hero.hp:
            self.draw_death_screen()
        elif self.area == "boss" and not self.boss.hp and self.end_timer > VICTORY_MESSAGE_DELAY:
            self.overlay("Herdeiro do Fogo Destruído", "R  retornar ao cemitério", (219, 176, 82))
        pygame.display.flip()

    def run(self):
        running, frames = True, 0
        while running:
            dt = min(self.clock.tick(FPS) / 1000, .033)
            running, jump = self.handle_events()
            self.update(dt, jump)
            self.draw()
            frames += 1
            if self.capture and frames == 40:
                pygame.image.save(self.screen, ROOT / "preview.png")
                running = False
        pygame.quit()


if __name__ == "__main__":
    try:
        Game("--capture" in sys.argv).run()
    except (pygame.error, FileNotFoundError) as error:
        print(f"Não foi possível iniciar o jogo: {error}")
        raise SystemExit(1)
