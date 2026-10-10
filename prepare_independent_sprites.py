"""Build isolated one-row animation strips from the independent 5x2 sources."""

from __future__ import annotations

from pathlib import Path
from statistics import median

import pygame


ROOT = Path(__file__).parent
SOURCE_DIR = ROOT / "assets" / "source_v5"
OUTPUT_DIR = ROOT / "assets" / "animations_v5"
GRID_COLUMNS = 5
GRID_ROWS = 2
ALPHA_THRESHOLD = 24
HORIZONTAL_PADDING = 16
TOP_PADDING = 16
BOTTOM_PADDING = 2
SAFETY_MARGIN = 8

SOURCES = {
    "hero": (
        98,
        (
            "idle",
            "walk",
            "dodge",
            "block",
            "drink",
            "death",
            "attack_a",
            "attack_b",
            "heavy_a",
            "heavy_b",
        ),
    ),
    "gundyr": (
        104,
        (
            "idle",
            "walk",
            "sweep_a",
            "sweep_b",
            "thrust_a",
            "thrust_b",
            "slam",
            "special",
        ),
    ),
}


def opaque_bbox(surface: pygame.Surface) -> pygame.Rect:
    mask = pygame.mask.from_surface(surface, ALPHA_THRESHOLD)
    rects = mask.get_bounding_rects()
    if not rects:
        return pygame.Rect(0, 0, 0, 0)
    result = rects[0].copy()
    for rect in rects[1:]:
        result.union_ip(rect)
    return result


def upper_body_anchor_x(surface: pygame.Surface, bbox: pygame.Rect) -> float:
    """Return a stable horizontal anchor using the helmet and shoulders.

    Centering a frame by its full bounds makes the body jump whenever the
    halberd reaches farther. The upper third excludes its blade and gives the
    walk cycle a visually stable body axis.
    """
    alpha = pygame.surfarray.array_alpha(surface)
    upper_bottom = bbox.top + max(1, round(bbox.height * 0.35))
    occupied_x = (alpha[:, bbox.top:upper_bottom] > ALPHA_THRESHOLD).nonzero()[0]
    if not len(occupied_x):
        return bbox.width / 2
    return float(median(occupied_x)) - bbox.left


def closest_clear_separator(values, nominal: int, radius: int) -> int:
    """Find a transparent line close to an expected invisible grid division."""
    low = max(1, nominal - radius)
    high = min(len(values) - 1, nominal + radius + 1)
    candidates = [index for index in range(low, high) if values[index] == 0]
    if candidates:
        return min(candidates, key=lambda index: abs(index - nominal))
    return min(
        range(low, high),
        key=lambda index: (values[index], abs(index - nominal)),
    )


def grid_boundaries(sheet: pygame.Surface):
    alpha = pygame.surfarray.array_alpha(sheet)
    occupied = alpha > ALPHA_THRESHOLD
    column_ink = occupied.sum(axis=1)
    row_ink = occupied.sum(axis=0)

    width, height = sheet.get_size()
    x_boundaries = [0]
    for column in range(1, GRID_COLUMNS):
        nominal = width * column // GRID_COLUMNS
        x_boundaries.append(
            closest_clear_separator(column_ink, nominal, width // 18)
        )
    x_boundaries.append(width)

    nominal_y = height // GRID_ROWS
    y_separator = closest_clear_separator(row_ink, nominal_y, height // 7)
    return x_boundaries, [0, y_separator, height]


def split_grid(sheet: pygame.Surface):
    x_boundaries, y_boundaries = grid_boundaries(sheet)
    frames = []
    metadata = []
    for row in range(GRID_ROWS):
        for column in range(GRID_COLUMNS):
            left, right = x_boundaries[column], x_boundaries[column + 1]
            top, bottom = y_boundaries[row], y_boundaries[row + 1]
            frame = sheet.subsurface((left, top, right - left, bottom - top)).copy()
            bbox = opaque_bbox(frame)
            if not bbox.width or not bbox.height:
                raise RuntimeError(f"empty pose at row {row + 1}, column {column + 1}")
            frames.append(frame)
            metadata.append((bbox, row))
    return frames, metadata


def build_strip(prefix: str, animation: str, target_neutral_height: int):
    source_prefix = "boss" if prefix == "gundyr" else prefix
    source_path = SOURCE_DIR / f"{source_prefix}_{animation}.png"
    sheet = pygame.image.load(source_path).convert_alpha()
    frames, metadata = split_grid(sheet)
    frame_scale_multipliers = [1.0] * len(frames)
    walk_key_heights = None

    # Use one clean armor/weapon pose as the calibrated rig's texture source.
    # The old sheet's grounded poses cannot produce a raised foot merely by
    # optical-flow interpolation; new bent-knee key poses are baked below.
    if prefix == "gundyr" and animation == "walk":
        walk_key_heights = [metadata[0][0].height, metadata[-1][0].height]
        frames, metadata, frame_scale_multipliers = frames[:1], metadata[:1], [1.0]

    # Death ends in a deliberately short lying pose. Scale from the initial
    # standing frame so the armor remains the same size as the other strips.
    if prefix == "hero" and animation == "death":
        anchor_heights = [metadata[0][0].height]
    elif walk_key_heights is not None:
        anchor_heights = walk_key_heights
    else:
        anchor_heights = [metadata[0][0].height, metadata[-1][0].height]
    scale = target_neutral_height / median(anchor_heights)

    lifts = [0.0] * len(frames)
    if prefix == "gundyr" and animation == "special":
        top_ground = median(metadata[index][0].bottom for index in (0, 1))
        bottom_ground = median(metadata[index][0].bottom for index in (6, 7, 8, 9))
        for index, (bbox, row) in enumerate(metadata):
            ground = top_ground if row == 0 else bottom_ground
            lifts[index] = max(0.0, ground - bbox.bottom)

    stable_body_anchor = prefix == "gundyr" and animation == "walk"
    prepared = []
    for frame, (bbox, _), lift, multiplier in zip(
        frames, metadata, lifts, frame_scale_multipliers
    ):
        anchor_x = (
            upper_body_anchor_x(frame, bbox)
            if stable_body_anchor
            else bbox.width / 2
        )
        cropped = frame.subsurface(bbox).copy()
        frame_scale = scale * multiplier
        size = (
            max(1, round(cropped.get_width() * frame_scale)),
            max(1, round(cropped.get_height() * frame_scale)),
        )
        scaled = pygame.transform.smoothscale(cropped, size)
        prepared.append(
            (
                scaled,
                round(lift * frame_scale),
                round(anchor_x * frame_scale),
            )
        )

    if stable_body_anchor:
        from rig_gundyr_walk import BODY_AXIS, SOURCE_SIZE, build_walk_keyframes

        cell_width, cell_height = SOURCE_SIZE
        body_axis = BODY_AXIS
    else:
        cell_width = (
            max(frame.get_width() for frame, _, _ in prepared)
            + HORIZONTAL_PADDING * 2
        )
        cell_height = (
            max(frame.get_height() + lift for frame, lift, _ in prepared)
            + TOP_PADDING
            + BOTTOM_PADDING
        )
    baseline = cell_height - BOTTOM_PADDING
    cells = []

    for index, (frame, lift, anchor) in enumerate(prepared):
        isolated_cell = pygame.Surface((cell_width, cell_height), pygame.SRCALPHA)
        destination = (
            body_axis - anchor
            if stable_body_anchor
            else (cell_width - frame.get_width()) // 2,
            baseline - lift - frame.get_height(),
        )
        isolated_cell.blit(frame, destination)

        content = opaque_bbox(isolated_cell)
        if (
            content.left < SAFETY_MARGIN
            or content.right > cell_width - SAFETY_MARGIN
            or content.top < SAFETY_MARGIN
            or content.bottom > cell_height - 1
        ):
            raise RuntimeError(
                f"{source_path.name} frame {index + 1} entered its safety border"
            )
        cells.append(isolated_cell)

    if stable_body_anchor:
        from interpolate_walk import interpolate_walk_cells

        cells = interpolate_walk_cells(build_walk_keyframes(cells[0]))

    strip = pygame.Surface((cell_width * len(cells), cell_height), pygame.SRCALPHA)
    for index, cell in enumerate(cells):
        content = opaque_bbox(cell)
        if (
            content.left < SAFETY_MARGIN
            or content.right > cell_width - SAFETY_MARGIN
            or content.top < SAFETY_MARGIN
            or content.bottom > cell_height - 1
        ):
            raise RuntimeError(f"{source_path.name} frame {index + 1} entered its safety border")
        strip.blit(cell, (index * cell_width, 0))

    output_path = OUTPUT_DIR / f"{prefix}_{animation}.png"
    pygame.image.save(strip, output_path)
    print(
        f"{output_path.name}: {len(cells)} frames, cell={cell_width}x{cell_height}, "
        f"source scale={scale:.3f}"
    )


def main():
    pygame.init()
    pygame.display.set_mode((1, 1), flags=pygame.HIDDEN)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for prefix, (target_height, animations) in SOURCES.items():
        for animation in animations:
            build_strip(prefix, animation, target_height)
    print(f"Independent animation strips saved to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
