"""Generate the hooded Hollow animation strips used by Ashen Trial."""

from __future__ import annotations

import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "assets" / "animations_v5"
CELL_W, CELL_H, FRAMES = 128, 120, 10
GROUND_Y = CELL_H - 2

INK = (12, 14, 20, 255)
DEEP_CLOTH = (25, 31, 47, 255)
CLOTH = (48, 58, 78, 255)
CLOTH_LIGHT = (72, 84, 108, 255)
BONE_DARK = (119, 113, 102, 255)
BONE = (190, 182, 163, 255)
BONE_LIGHT = (224, 217, 198, 255)
BRONZE_DARK = (82, 59, 30, 255)
BRONZE = (158, 111, 52, 255)
BRONZE_LIGHT = (210, 168, 92, 255)
VERDIGRIS = (67, 100, 84, 255)


def poly(draw, points, fill, outline=INK, width=1):
    draw.polygon([(round(x), round(y)) for x, y in points], fill=fill)
    draw.line([(round(x), round(y)) for x, y in (*points, points[0])], fill=outline, width=width, joint="curve")


def limb(draw, points, fill, width):
    pts = [(round(x), round(y)) for x, y in points]
    draw.line(pts, fill=INK, width=width + 2, joint="curve")
    draw.line(pts, fill=fill, width=width, joint="curve")


def sword(draw, hand, angle, dropped=False):
    length = 31 if not dropped else 34
    dx, dy = math.cos(angle), math.sin(angle)
    hx, hy = hand
    tip = (hx + dx * length, hy + dy * length)
    px, py = -dy, dx
    base = (hx + dx * 5, hy + dy * 5)
    blade = [
        (base[0] + px * 3.5, base[1] + py * 3.5),
        (tip[0] + px * 2, tip[1] + py * 2),
        (tip[0] + dx * 3, tip[1] + dy * 3),
        (tip[0] - px * 2, tip[1] - py * 2),
        (base[0] - px * 3.5, base[1] - py * 3.5),
    ]
    poly(draw, blade, BRONZE, width=2)
    draw.line((round(base[0] + px), round(base[1] + py), round(tip[0] + px), round(tip[1] + py)), fill=BRONZE_LIGHT, width=1)
    draw.line((round(hx - px * 5), round(hy - py * 5), round(hx + px * 5), round(hy + py * 5)), fill=BRONZE_DARK, width=3)
    draw.line((round(hx - dx * 7), round(hy - dy * 7), round(hx + dx * 3), round(hy + dy * 3)), fill=(55, 42, 29, 255), width=3)
    draw.point((round(tip[0] - px), round(tip[1] - py)), fill=VERDIGRIS)


def pose(animation, index):
    t = index / (FRAMES - 1)
    phase = math.tau * t
    values = {
        "bob": math.sin(phase) * .8,
        "lean": 4,
        "step": 0,
        "arm": .95,
        "head": 0,
        "sword": 1.02,
        "death": 0,
        "ash": 0,
    }
    if animation == "idle":
        values["arm"] += math.sin(phase) * .05
        values["head"] = math.sin(phase) * .8
    elif animation == "walk":
        values["bob"] = abs(math.sin(phase)) * 2
        values["step"] = math.sin(phase) * 7
        values["arm"] += math.sin(phase + math.pi) * .12
    elif animation == "attack":
        if index <= 4:
            p = index / 4
            values["lean"] = 4 - p * 5
            values["arm"] = .95 + p * 2.8
            values["sword"] = 1.02 + p * 2.85
        elif index <= 7:
            p = (index - 5) / 2
            values["lean"] = 9 + p * 4
            values["arm"] = -.55 + p * .45
            values["sword"] = -.7 + p * .45
        else:
            p = index - 8
            values["lean"] = 9 - p * 4
            values["arm"] = .15 + p * .45
            values["sword"] = .05 + p * .5
    elif animation == "hurt":
        values["lean"] = -8 - math.sin(t * math.pi) * 7
        values["head"] = -3
        values["arm"] = 1.4
    elif animation == "stagger":
        values["lean"] = -11 - math.sin(t * math.pi) * 4
        values["bob"] = 3
        values["arm"] = 1.7 + math.sin(phase) * .25
        values["sword"] = 1.35
    elif animation == "death":
        values["death"] = min(1, t * 1.25)
        values["lean"] = -4 - values["death"] * 30
        values["bob"] = values["death"] * 35
        values["arm"] = 1.2 + values["death"]
        values["sword"] = .18
        values["ash"] = max(0, (t - .35) / .65)
    return values


def draw_frame(animation, index):
    image = Image.new("RGBA", (CELL_W, CELL_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    p = pose(animation, index)
    death = p["death"]
    cx = 61 + p["lean"]
    base = GROUND_Y - p["bob"]

    if death > .72:
        body_y = 83 + (death - .72) * 42
        poly(draw, [(33, body_y), (78, body_y - 10), (100, base - 1), (49, base - 1)], DEEP_CLOTH)
        draw.ellipse((45, body_y - 17, 64, body_y + 2), fill=INK)
        draw.ellipse((49, body_y - 14, 61, body_y - 2), fill=BONE_DARK)
        sword(draw, (78, base - 6), .08, True)
    else:
        left_foot = (cx - 11 - p["step"], base)
        right_foot = (cx + 10 + p["step"], base)
        limb(draw, [(cx - 7, base - 34), (cx - 9, base - 13), left_foot], BONE_DARK, 5)
        limb(draw, [(cx + 7, base - 34), (cx + 9, base - 13), right_foot], BONE_DARK, 5)
        poly(draw, [(left_foot[0] - 7, base - 3), (left_foot[0] + 5, base - 4), (left_foot[0] + 8, base), (left_foot[0] - 7, base)], BONE)
        poly(draw, [(right_foot[0] - 5, base - 4), (right_foot[0] + 8, base - 3), (right_foot[0] + 9, base), (right_foot[0] - 6, base)], BONE)

        hem = base - 3
        robe = [
            (cx - 17, base - 70), (cx + 12, base - 72), (cx + 22, hem - 5),
            (cx + 12, hem - 1), (cx + 5, hem - 7), (cx - 2, hem - 1),
            (cx - 11, hem - 6), (cx - 22, hem),
        ]
        poly(draw, robe, CLOTH)
        poly(draw, [(cx - 17, base - 69), (cx - 27, base - 55), (cx - 20, hem - 7), (cx - 7, base - 55)], DEEP_CLOTH)
        draw.line((cx - 5, base - 64, cx - 8, hem - 7), fill=CLOTH_LIGHT, width=1)
        draw.line((cx + 5, base - 64, cx + 11, hem - 9), fill=(35, 43, 61, 255), width=2)

        shoulder_y = base - 67
        back_hand = (cx - 24, base - 40)
        limb(draw, [(cx - 10, shoulder_y), (cx - 19, base - 54), back_hand], CLOTH, 6)
        draw.ellipse((back_hand[0] - 3, back_hand[1] - 3, back_hand[0] + 4, back_hand[1] + 5), fill=BONE, outline=INK)

        hand = (cx + 20 + math.cos(p["arm"]) * 10, shoulder_y + 17 + math.sin(p["arm"]) * 12)
        elbow = ((cx + 10 + hand[0]) / 2, shoulder_y + 7)
        limb(draw, [(cx + 9, shoulder_y), elbow, hand], BONE_DARK, 5)
        draw.ellipse((hand[0] - 3, hand[1] - 3, hand[0] + 4, hand[1] + 4), fill=BONE_LIGHT, outline=INK)
        sword(draw, hand, p["sword"])

        head_x, head_y = cx - 3 + p["head"], base - 87
        poly(draw, [(head_x - 15, head_y - 3), (head_x - 9, head_y - 17), (head_x + 7, head_y - 20), (head_x + 16, head_y - 7), (head_x + 12, head_y + 12), (head_x - 12, head_y + 11)], DEEP_CLOTH)
        draw.ellipse((head_x - 8, head_y - 10, head_x + 8, head_y + 9), fill=BONE, outline=INK, width=1)
        draw.ellipse((head_x - 5, head_y - 5, head_x - 1, head_y), fill=(23, 21, 23, 255))
        draw.ellipse((head_x + 3, head_y - 5, head_x + 7, head_y), fill=(23, 21, 23, 255))
        draw.ellipse((head_x - 2, head_y + 2, head_x + 5, head_y + 8), fill=(45, 35, 35, 255))
        draw.line((head_x - 10, head_y + 10, head_x + 11, head_y + 10), fill=CLOTH_LIGHT, width=1)

    rng = random.Random(4100 + index + sum(map(ord, animation)))
    for _ in range(24):
        x, y = rng.randrange(30, 99), rng.randrange(22, 116)
        if image.getpixel((x, y))[3] > 0:
            draw.point((x, y), fill=(12, 15, 23, rng.randrange(55, 130)))
    for particle in range(round(p["ash"] * 10)):
        x = 45 + rng.randrange(45)
        y = 104 - rng.randrange(5, 45) - particle
        draw.point((x, y), fill=(120, 111, 100, 180))
    bounds = image.getchannel("A").getbbox()
    if bounds:
        normalized = Image.new("RGBA", image.size, (0, 0, 0, 0))
        normalized.alpha_composite(image, (0, GROUND_Y - bounds[3]))
        image = normalized
    return image


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    animations = ("idle", "walk", "attack", "hurt", "stagger", "death")
    rendered = {}
    for animation in animations:
        frames = [draw_frame(animation, index) for index in range(FRAMES)]
        strip = Image.new("RGBA", (CELL_W * FRAMES, CELL_H), (0, 0, 0, 0))
        for index, frame in enumerate(frames):
            strip.alpha_composite(frame, (index * CELL_W, 0))
        strip.save(OUTPUT / f"hollow_{animation}.png")
        rendered[animation] = strip

    label_w = 125
    preview = Image.new("RGBA", (label_w + CELL_W * FRAMES, CELL_H * 7), (10, 12, 17, 255))
    preview_draw = ImageDraw.Draw(preview)
    for row, animation in enumerate(animations):
        preview_draw.text((10, row * CELL_H + 48), animation.upper(), fill=(205, 198, 185, 255))
        preview.alpha_composite(rendered[animation], (label_w, row * CELL_H))

    hero = Image.open(OUTPUT / "hero_idle.png").convert("RGBA").crop((0, 0, 145, 119))
    gundyr = Image.open(OUTPUT / "gundyr_idle.png").convert("RGBA").crop((0, 0, 144, 122))
    row_y = CELL_H * 6
    preview_draw.text((10, row_y + 48), "ESCALA", fill=(205, 198, 185, 255))
    preview.alpha_composite(hero, (label_w + 70, row_y))
    preview.alpha_composite(rendered["idle"].crop((0, 0, CELL_W, CELL_H)), (label_w + 330, row_y))
    preview.alpha_composite(gundyr, (label_w + 570, row_y - 2))
    preview_draw.text((label_w + 75, row_y + 4), "HERÓI", fill=(220, 210, 192, 255))
    preview_draw.text((label_w + 333, row_y + 4), "HOLLOW", fill=(220, 210, 192, 255))
    preview_draw.text((label_w + 575, row_y + 4), "GUNDYR", fill=(220, 210, 192, 255))
    preview.save(ROOT / "preview_hollow.png")


if __name__ == "__main__":
    main()
