"""Pack newly drawn Gundyr poses without rigging, warping or interpolation.

The source is a generated 4x4 sheet. A connected opaque silhouette identifies
each complete sprite (body AND weapon); explicit pelvis registration keeps
the animation origin stable. Only crop, uniform whole-pose scale and padding
are used. Color/material corrections are painted in the generated source,
not applied as a runtime tint. Row calibration corrects atlas-size variation;
the walk's bent silhouette is deliberately shorter than the upright idle.
Runtime consumes sixteen independent PNGs, never neighboring atlas cells.
"""

from __future__ import annotations

from pathlib import Path

import pygame


ROOT = Path(__file__).parent
SOURCE = ROOT / "assets" / "source_v6" / "gundyr_walk_consistent.png"
OUTPUT = ROOT / "assets" / "animations_v6" / "gundyr_walk"
FRAME_COUNT = 16
CELL_SIZE = (256, 124)
BODY_AXIS = 104
BASELINE = CELL_SIZE[1] - 2
ALPHA_THRESHOLD = 24
MIN_SPRITE_PIXELS = 500
# Artist registration points, in the corrected source's coordinates.
# These identify the pelvis, not the changing blade extent or head tilt.
PELVIS_X = (
    212, 629, 1044, 1458,
    214, 625, 1056, 1463,
    218, 627, 1046, 1463,
    218, 637, 1053, 1471,
)
SOURCE_SIZE = (1671, 941)
# AI sheets can draw later rows at a smaller pixel scale. Correct each row as
# a WHOLE, identically on both axes and on all four poses in it; do not stretch
# a limb or scale individual poses to equal heights. Their drawn bob remains.
# Matching a crouched walk's full height to the 104px upright idle enlarged
# its helmet, pauldrons and blade. At 86px their painted proportions match
# the idle while the inclined torso and flexed knees keep their shorter pose.
# This remains a single scale per ROW, not a per-frame height equalizer.
WALK_POSE_HEIGHT = 86
ROW_SCALES = tuple(WALK_POSE_HEIGHT / height for height in (172.5, 175, 176, 168.5))


def source_drawings(sheet: pygame.Surface):
    """Locate sixteen separate COMPLETE drawings and order them row-major."""
    if sheet.get_size() != SOURCE_SIZE:
        raise ValueError("The drawn walk source changed size; review its registration points")
    mask = pygame.mask.from_surface(sheet, ALPHA_THRESHOLD)
    parts = mask.connected_components(MIN_SPRITE_PIXELS)
    if len(parts) != FRAME_COUNT:
        raise ValueError(f"Expected {FRAME_COUNT} separate full-body drawings, found {len(parts)}")
    drawings = [(part.get_bounding_rects()[0], part) for part in parts]
    drawings.sort(key=lambda item: item[0].centery)
    ordered = []
    for row in range(4):
        group = sorted(drawings[row * 4:(row + 1) * 4], key=lambda item: item[0].centerx)
        for (first, _), (second, _) in zip(group, group[1:]):
            if first.right >= second.left:
                raise ValueError("Drawn sprites overlap horizontally; regenerate with wider gutters")
        # A diagonal blade's rectangular bounds can share a row with the next
        # helmet even though their actual silhouettes never touch. Extract by
        # component ownership below, not by an assumed rectangular grid.
        ordered.extend(group)
    for index, (rect, _) in enumerate(ordered):
        if not rect.left < PELVIS_X[index] < rect.right:
            raise ValueError(f"Invalid pelvis registration for drawn pose {index:02}")
        if rect.left <= 0 or rect.top <= 0 or rect.right >= sheet.get_width() or rect.bottom >= sheet.get_height():
            raise ValueError(f"Drawn pose {index:02} is cropped by the source border")
    return ordered


def source_rects(sheet: pygame.Surface) -> list[pygame.Rect]:
    return [rect for rect, _ in source_drawings(sheet)]


def pack_frames(sheet: pygame.Surface) -> list[pygame.Surface]:
    frames = []
    for index, (bounds, component) in enumerate(source_drawings(sheet)):
        # The original generated drawing is retained, including all details
        # inside the complete silhouette. No compositing of limbs or poses.
        drawing = sheet.subsurface(bounds).copy()
        # Retain this drawing's original alpha, including the one-pixel soft
        # edge, but exclude pixels owned by another pose inside its rectangle.
        # This is silhouette extraction only; no limb or painted pixel moves.
        ownership = component.copy()
        for delta in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            ownership.draw(component, delta)
        stencil = ownership.to_surface(setcolor=(255, 255, 255, 255), unsetcolor=(0, 0, 0, 0))
        drawing.blit(stencil.subsurface(bounds), (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        scale = ROW_SCALES[index // 4]
        size = (round(bounds.width * scale), round(bounds.height * scale))
        scaled = pygame.transform.smoothscale(drawing, size)
        scaled_bounds = scaled.get_bounding_rect(min_alpha=ALPHA_THRESHOLD)
        frame = pygame.Surface(CELL_SIZE, pygame.SRCALPHA)
        destination = (
            BODY_AXIS - round((PELVIS_X[index] - bounds.left) * scale),
            BASELINE - scaled_bounds.bottom,
        )
        visible = scaled_bounds.move(destination)
        if visible.left < 8 or visible.right > CELL_SIZE[0] - 8 or visible.top < 8:
            raise ValueError(f"Drawn pose {index:02} would lose a boot or blade in the output cell")
        frame.blit(scaled, destination)
        frames.append(frame)
    return frames


def export_walk(output: Path = OUTPUT) -> list[pygame.Surface]:
    sheet = pygame.image.load(SOURCE).convert_alpha()
    frames = pack_frames(sheet)
    output.mkdir(parents=True, exist_ok=True)
    for index, frame in enumerate(frames):
        pygame.image.save(frame, output / f"{index:02}.png")
    print(f"Gundyr: {len(frames)} drawn poses, individual {CELL_SIZE[0]}x{CELL_SIZE[1]} PNGs in {output}")
    return frames


def main():
    pygame.init()
    pygame.display.set_mode((1, 1), flags=pygame.HIDDEN)
    try:
        export_walk()
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
