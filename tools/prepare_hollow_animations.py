"""Normalize complete generated Hollow frames into the runtime strip format.

Every source cell already contains one fully painted character. This script
never separates, redraws or recomposes body parts; it only places the ten whole
frames from a 5x2 source sheet into the one-row format used by SpriteArt.
"""

from __future__ import annotations

import time
from pathlib import Path

import pygame
from PIL import Image, ImageChops, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "assets" / "source_animations_v4"
OUTPUT_DIR = ROOT / "assets" / "animations_v5"
ANIMATIONS = ("idle", "walk", "run", "attack", "hurt", "stagger", "death")
CELL_W, DEFAULT_CELL_H = 208, 120
PADDING = 3


def complete_frames(path: Path, expected: int) -> list[Image.Image]:
    """Extract whole connected character silhouettes without slicing anatomy."""
    source = Image.open(path).convert("RGBA")
    surface = pygame.image.frombytes(source.tobytes(), source.size, "RGBA")
    components = pygame.mask.from_surface(surface, 24).connected_components(2000)
    if len(components) != expected:
        raise ValueError(f"Expected {expected} complete figures in {path}, found {len(components)}")

    def order(component):
        rect = component.get_bounding_rects()[0]
        row = 0 if expected == 5 or rect.centery < source.height / 2 else 1
        return row, rect.centerx

    frames = []
    source_alpha = source.getchannel("A")
    for component in sorted(components, key=order):
        rect = component.get_bounding_rects()[0]
        mask_surface = component.to_surface(
            setcolor=(255, 255, 255, 255),
            unsetcolor=(0, 0, 0, 0),
        )
        mask_image = Image.frombytes(
            "RGBA",
            source.size,
            pygame.image.tobytes(mask_surface, "RGBA"),
        ).getchannel("A")
        isolated = source.copy()
        isolated.putalpha(ImageChops.multiply(source_alpha, mask_image))
        frames.append(isolated.crop((rect.left, rect.top, rect.right, rect.bottom)))
    return frames


def normalize_complete_frame(frame: Image.Image, scale: float, cell_height: int) -> Image.Image:
    """Scale and ground one whole character without altering its anatomy."""
    size = (max(1, round(frame.width * scale)), max(1, round(frame.height * scale)))
    frame = frame.resize(size, Image.Resampling.LANCZOS)
    resized_bounds = frame.getchannel("A").getbbox()
    if resized_bounds:
        frame = frame.crop(resized_bounds)
    ground_y = cell_height - 2
    cell = Image.new("RGBA", (CELL_W, cell_height), (0, 0, 0, 0))
    cell.alpha_composite(frame, ((CELL_W - frame.width) // 2, ground_y - frame.height))
    return cell


def build_strip(animation: str) -> Image.Image:
    cell_height = 200 if animation == "attack" else DEFAULT_CELL_H
    if animation == "attack":
        raw_frames = complete_frames(SOURCE_DIR / "hollow_attack_a.png", 5)
        raw_frames.extend(complete_frames(SOURCE_DIR / "hollow_attack_b.png", 5))
    else:
        raw_frames = complete_frames(SOURCE_DIR / f"hollow_{animation}.png", 10)
    scale = min(
        (CELL_W - PADDING * 2) / max(frame.width for frame in raw_frames),
        (cell_height - 2 - PADDING) / max(frame.height for frame in raw_frames),
    )
    frames = [normalize_complete_frame(frame, scale, cell_height) for frame in raw_frames]
    strip = Image.new("RGBA", (CELL_W * len(frames), cell_height), (0, 0, 0, 0))
    for index, frame in enumerate(frames):
        strip.alpha_composite(frame, (index * CELL_W, 0))
    return strip


def save_png(image: Image.Image, path: Path) -> None:
    """Atomically replace a runtime strip, tolerating brief Windows scanners."""
    temporary = path.with_name(f"{path.stem}.new.png")
    image.save(temporary)
    for attempt in range(5):
        try:
            temporary.replace(path)
            return
        except OSError:
            if attempt == 4:
                raise
            time.sleep(.08 * (attempt + 1))


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    strips = {}
    for animation in ANIMATIONS:
        strip = build_strip(animation)
        save_png(strip, OUTPUT_DIR / f"hollow_{animation}.png")
        strips[animation] = strip

    label_w = 120
    preview_row_h = 200
    preview = Image.new("RGBA", (label_w + CELL_W * 10, preview_row_h * len(ANIMATIONS)), (10, 12, 17, 255))
    labels = ImageDraw.Draw(preview)
    for row, animation in enumerate(ANIMATIONS):
        row_y = row * preview_row_h
        labels.text((10, row_y + 70), animation.upper(), fill=(215, 207, 193, 255))
        preview.alpha_composite(strips[animation], (label_w, row_y + preview_row_h - strips[animation].height))
    preview.save(ROOT / "preview_hollow.png")


if __name__ == "__main__":
    main()
