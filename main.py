"""Ashen Penitent - a side-scrolling pixel-art boss duel made with Pygame."""

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
HEAL_DURATION = 1.45
HEAL_APPLY_TIME = .78
DEATH_ANIMATION_DURATION = 1.15
ROOT = Path(__file__).parent
ANIMATION_FRAME_COUNTS = {("gundyr", "walk"): 20}


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
    def _strips(prefix, animation_names, scale):
        output = {}
        for name in animation_names:
            independent = ROOT / "assets" / "animations_v5" / f"{prefix}_{name}.png"
            legacy = ROOT / "assets" / "animations_v3" / f"{prefix}_{name}.png"
            path = independent if independent.exists() else legacy
            strip = pygame.image.load(path).convert_alpha()
            frame_count = ANIMATION_FRAME_COUNTS.get((prefix, name), 10)
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
    def __init__(self):
        self.pos = pygame.Vector2(300, GROUND)
        self.velocity = pygame.Vector2()
        self.facing = 1
        self.hp = self.max_hp = 110.0
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

    def update(self, dt, move, jump_pressed, defending):
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
        self.pos.x = clamp(self.pos.x, LEFT_WALL + 28, RIGHT_WALL - 28)

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
            return hitbox, damage
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
            return hitbox, damage
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
        self.pos.x = clamp(self.pos.x, LEFT_WALL + 65, RIGHT_WALL - 65)
        return events

    def draw(self, surface, sprites, offset):
        if self.state == "dead" and self.dead_time > 2.3:
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
        if self.state == "sweep":
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
        if name in ("idle", "walk"):
            # The 20-frame walk runs at double the old sampling rate, keeping
            # the same cycle duration while showing the new transition poses.
            speed = 18 if name == "walk" else 4
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
        if self.state == "dead":
            frame = pygame.transform.rotate(frame, -70 * self.facing)
        # The scaled strips retain three transparent pixels below the boots.
        # Four pixels place the visible soles one pixel into the shadow/ground.
        rect = frame.get_rect(midbottom=(pos.x, pos.y + 4))
        surface.blit(frame, rect)
        if self.state == "stagger":
            draw_text(surface, pygame.font.SysFont("georgia", 18), "VULNERÁVEL", (pos.x, pos.y - 175), (226, 182, 87), "center")


class Game:
    def __init__(self, capture=False):
        pygame.init()
        pygame.display.set_caption("Ashen Penitent")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.font_small = pygame.font.SysFont("georgia", 17)
        self.font_ui = pygame.font.SysFont("georgia", 23)
        self.font_large = pygame.font.SysFont("georgia", 62)
        self.font_death = pygame.font.SysFont("georgia", 82)
        self.art = SpriteArt()
        self.background = self.build_background()
        self.death_vignette = self.build_death_vignette()
        self.capture = capture
        self.show_hitboxes = True
        self.restart()

    def restart(self):
        self.hero, self.boss = Hero(), Gundyr()
        self.particles, self.waves = [], []
        self.shake = self.freeze = self.end_timer = 0.0
        self.help_time, self.paused = 8.0, False

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

    def handle_events(self):
        jump = False
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False, jump
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.paused = not self.paused
                elif event.key == pygame.K_F3:
                    self.show_hitboxes = not self.show_hitboxes
                elif event.key == pygame.K_h:
                    self.help_time = 999 if self.help_time < 20 else 0
                elif event.key == pygame.K_r and (not self.hero.hp or not self.boss.hp):
                    self.restart()
                elif not self.paused and self.hero.hp and self.boss.hp:
                    if event.key in (pygame.K_w, pygame.K_UP):
                        jump = True
                    elif event.key in (pygame.K_SPACE, pygame.K_LSHIFT):
                        self.hero.dodge(self.movement())
                    elif event.key == pygame.K_q:
                        self.hero.parry()
                    elif event.key == pygame.K_e:
                        self.hero.heal()
            if event.type == pygame.MOUSEBUTTONDOWN and not self.paused and self.hero.hp and self.boss.hp:
                if event.button == 1:
                    self.hero.attack()
                elif event.button == 3:
                    self.hero.attack(True)
        return True, jump

    def update(self, dt, jump):
        if self.paused:
            return
        self.help_time = max(0, self.help_time - dt)
        if self.freeze > 0:
            self.freeze -= dt
            return
        defending = pygame.key.get_pressed()[pygame.K_f]
        self.hero.update(dt, self.movement(), jump, defending)
        if self.hero.heal_effect:
            self.burst(
                self.hero.pos - pygame.Vector2(0, 54),
                (238, 147, 35),
                24,
                125,
            )
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
            if self.boss.receive(damage):
                self.freeze, self.shake = ((.09, 9) if damage > 20 else (.05, 5))
                self.burst(self.boss.pos - pygame.Vector2(self.hero.facing * 45, 85), (153, 37, 36), 15)
        # During a dodge the hero can roll through the boss. Body separation
        # resumes as soon as the roll ends.
        if abs(self.hero.pos.x - self.boss.pos.x) < 72 and self.hero.grounded and self.hero.state != "dodge":
            direction = 1 if self.hero.pos.x > self.boss.pos.x else -1
            overlap = 72 - abs(self.hero.pos.x - self.boss.pos.x)
            self.hero.pos.x += direction * overlap * .72
            self.boss.pos.x -= direction * overlap * .28
        self.particles = [particle for particle in self.particles if particle.update(dt)]
        for wave in self.waves:
            wave[1] += 360 * dt
            wave[2] -= dt
        self.waves = [wave for wave in self.waves if wave[2] > 0]
        self.shake = max(0, self.shake - 24 * dt)
        if not self.hero.hp or not self.boss.hp:
            self.end_timer += dt

    def draw_bar(self, rect, ratio, color):
        pygame.draw.rect(self.screen, (5, 5, 7), rect.inflate(8, 8))
        pygame.draw.rect(self.screen, (48, 43, 44), rect)
        filled = rect.copy()
        filled.width = int(rect.width * clamp(ratio, 0, 1))
        if filled.width:
            pygame.draw.rect(self.screen, color, filled)
            pygame.draw.line(self.screen, tuple(min(255, c + 35) for c in color), filled.topleft, filled.topright, 2)
        pygame.draw.rect(self.screen, (116, 101, 89), rect, 1)

    def draw_hud(self):
        panel = pygame.Surface((390, 118), pygame.SRCALPHA)
        panel.fill((4, 4, 6, 180))
        self.screen.blit(panel, (20, 17))
        pygame.draw.circle(self.screen, (25, 22, 27), (65, 65), 37)
        pygame.draw.circle(self.screen, (148, 122, 76), (65, 65), 37, 3)
        pygame.draw.polygon(self.screen, (178, 37, 39), [(65, 39), (76, 64), (65, 93), (54, 64)])
        self.draw_bar(pygame.Rect(116, 37, 270, 19), self.hero.hp / self.hero.max_hp, (150, 31, 39))
        self.draw_bar(pygame.Rect(116, 69, 238, 13), self.hero.stamina / self.hero.max_stamina, (46, 128, 68))
        icon_rect = self.art.estus_icon.get_rect(midleft=(113, 111))
        self.screen.blit(self.art.estus_icon, icon_rect)
        draw_text(
            self.screen,
            self.font_small,
            f"ESTUS   × {self.hero.flasks}",
            (160, 99),
            (222, 174, 80),
        )
        if self.boss.state != "intro" or self.boss.timer > .45:
            rect = pygame.Rect(205, HEIGHT - 66, WIDTH - 410, 18)
            self.draw_bar(rect, self.boss.hp / self.boss.max_hp, (128, 25, 33))
            draw_text(self.screen, self.font_ui, "IUDEX GUNDYR", (rect.left, rect.top - 34))
            draw_text(self.screen, self.font_small, f"FASE {self.boss.phase}", (rect.right, rect.top - 28), (161, 149, 136), "topright")

    def overlay(self, title, subtitle, color):
        veil = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        veil.fill((5, 4, 7, 182))
        self.screen.blit(veil, (0, 0))
        draw_text(self.screen, self.font_large, title, (WIDTH // 2, HEIGHT // 2 - 18), color, "center")
        draw_text(self.screen, self.font_ui, subtitle, (WIDTH // 2, HEIGHT // 2 + 51), (193, 181, 168), "center")

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
        box(self.boss.hurt_box(), (255, 155, 45))
        hero_attack, _ = self.hero.attack_box()
        box(hero_attack, (45, 235, 100))
        box(self.boss.attack_box(), (255, 45, 65))
        self.screen.blit(layer, (0, 0))

        legend = pygame.Surface((198, 91), pygame.SRCALPHA)
        legend.fill((4, 4, 6, 190))
        items = (
            ("JOGADOR", (45, 145, 255)),
            ("GUNDYR", (255, 155, 45)),
            ("ATAQUE SEU", (45, 235, 100)),
            ("ATAQUE CHEFE", (255, 45, 65)),
        )
        for index, (label, color) in enumerate(items):
            y = 8 + index * 20
            pygame.draw.rect(legend, color, (9, y + 3, 16, 10), 2)
            legend.blit(self.font_small.render(label, True, (210, 202, 190)), (32, y))
        self.screen.blit(legend, (WIDTH - 218, 181))

    def draw(self):
        offset = pygame.Vector2()
        if self.shake:
            offset.xy = random.uniform(-self.shake, self.shake), random.uniform(-self.shake, self.shake)
        self.screen.blit(self.background, offset)
        for center, radius, life in self.waves:
            pygame.draw.ellipse(self.screen, (145, 43, 39), (center.x - radius + offset.x, GROUND - radius * .14 + offset.y, radius * 2, radius * .28), 4)
        for _, actor in sorted(((self.hero.pos.x, self.hero), (self.boss.pos.x, self.boss)), key=lambda item: item[0]):
            actor.draw(self.screen, self.art.hero if actor is self.hero else self.art.gundyr, offset)
        for particle in self.particles:
            particle.draw(self.screen, offset)
        self.draw_debug_hitboxes(offset)
        self.draw_hud()
        if self.help_time:
            box = pygame.Surface((670, 151), pygame.SRCALPHA)
            box.fill((5, 5, 7, 224))
            self.screen.blit(box, (WIDTH // 2 - 335, 18))
            pygame.draw.rect(self.screen, (117, 96, 75), (WIDTH // 2 - 335, 18, 670, 151), 1)
            draw_text(self.screen, self.font_ui, "DUELO LATERAL — SEM LOCK-ON", (WIDTH // 2, 32), anchor="midtop")
            draw_text(self.screen, self.font_small, "A/D mover  •  W pular  •  ESPAÇO rolar  •  F defender à frente", (WIDTH // 2, 70), (192, 184, 174), "midtop")
            draw_text(self.screen, self.font_small, "ESQ atacar  •  DIR golpe forte  •  Q aparar  •  E curar", (WIDTH // 2, 99), (192, 184, 174), "midtop")
            draw_text(self.screen, self.font_small, "Costas ignoram o escudo  •  F3 hitboxes  •  H oculta ajuda", (WIDTH // 2, 127), (164, 154, 143), "midtop")
        if self.paused:
            self.overlay("PAUSADO", "ESC para continuar", (214, 203, 186))
        elif not self.hero.hp:
            self.draw_death_screen()
        elif not self.boss.hp and self.end_timer > .8:
            self.overlay("CULPA PURIFICADA", "R  lutar novamente", (219, 176, 82))
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
