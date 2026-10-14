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

BOSS_ATTACKS = frozenset((
    "sweep_a", "sweep_b", "thrust_a", "thrust_b", "slam", "special"
))

# The source paintings overlap in a few places, so some neighboring weapons
# are already fused to a pose before any grid slicing. These small regions are
# the *other* pose's weapon/leg, measured in the exported cell's coordinates.
# Keep them explicit: a broad automatic crop would also remove the real axe.
BOSS_SHEET_BLEED = {
    ("sweep_a", 5): ((145, 120, 49, 36),),
    ("sweep_a", 6): ((145, 120, 49, 36),),
    ("sweep_b", 0): ((128, 0, 55, 72),),
    ("sweep_b", 1): ((0, 88, 64, 36), (160, 0, 23, 80)),
    ("sweep_b", 2): ((0, 105, 30, 19), (145, 100, 38, 24)),
    ("sweep_b", 3): ((0, 106, 61, 18),),
    ("sweep_b", 5): ((147, 100, 36, 24),),
    ("sweep_b", 6): ((147, 100, 36, 24),),
    ("thrust_a", 1): ((142, 0, 52, 64),),
    ("thrust_b", 1): ((0, 119, 81, 42),),
    ("thrust_b", 3): ((150, 120, 83, 41),),
    ("thrust_b", 6): ((158, 119, 75, 42),),
    ("thrust_b", 7): ((0, 80, 20, 81),),
}

# When silhouettes actually overlap, no crop can recover the hidden pixels.
# Reuse the closest intact attack pose rather than displaying two axe heads.
BOSS_FRAME_REPLACEMENTS = {
    ("sweep_a", 6): 5,
    ("sweep_b", 6): 5,
    ("sweep_b", 7): 8,
    ("thrust_a", 3): 4,
    ("thrust_a", 6): 8,
    ("thrust_a", 7): 8,
    ("thrust_b", 4): 5,
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


def split_grid(sheet: pygame.Surface, *, separate_rows: bool = False):
    x_boundaries, y_boundaries = grid_boundaries(sheet)
    row_boundaries = []
    if separate_rows:
        occupied = pygame.surfarray.array_alpha(sheet) > ALPHA_THRESHOLD
        width = sheet.get_width()
        for top, bottom in zip(y_boundaries, y_boundaries[1:]):
            row_ink = occupied[:, top:bottom].sum(axis=1)
            cuts = [0]
            for column in range(1, GRID_COLUMNS):
                nominal = width * column // GRID_COLUMNS
                cut = closest_clear_separator(row_ink, nominal, width // 8)
                if row_ink[cut]:
                    raise RuntimeError(
                        f"row {len(row_boundaries) + 1}, column {column}: "
                        "no transparent gap between poses"
                    )
                cuts.append(cut)
            cuts.append(width)
            row_boundaries.append(cuts)
    frames = []
    metadata = []
    for row in range(GRID_ROWS):
        boundaries = row_boundaries[row] if separate_rows else x_boundaries
        for column in range(GRID_COLUMNS):
            left, right = boundaries[column], boundaries[column + 1]
            top, bottom = y_boundaries[row], y_boundaries[row + 1]
            frame = sheet.subsurface((left, top, right - left, bottom - top)).copy()
            bbox = opaque_bbox(frame)
            if not bbox.width or not bbox.height:
                raise RuntimeError(f"empty pose at row {row + 1}, column {column + 1}")
            frames.append(frame)
            metadata.append((bbox, row))
    return frames, metadata


def split_connected_poses(sheet: pygame.Surface):
    """Keep each boss and halberd together when their horizontal ranges overlap."""
    width = sheet.get_width()
    _, y_boundaries = grid_boundaries(sheet)
    frames = []
    metadata = []

    for row, (top, bottom) in enumerate(zip(y_boundaries, y_boundaries[1:])):
        region = sheet.subsurface((0, top, width, bottom - top))
        mask = pygame.mask.from_surface(region, ALPHA_THRESHOLD)
        components = sorted(
            mask.connected_components(700),
            key=lambda component: component.get_bounding_rects()[0].left,
        )
        if len(components) not in (GRID_COLUMNS - 1, GRID_COLUMNS):
            raise RuntimeError(
                f"boss row {row + 1}: expected 4 or 5 figures, found {len(components)}"
            )

        joined = None
        if len(components) == GRID_COLUMNS - 1:
            joined = max(
                range(len(components)),
                key=lambda index: components[index].get_bounding_rects()[0].width,
            )
            joined_width = components[joined].get_bounding_rects()[0].width
            if joined_width < width // 3:
                raise RuntimeError(f"boss row {row + 1}: cannot locate touching figures")

        source_alpha = pygame.surfarray.array_alpha(region)
        selections = []
        for index, component in enumerate(components):
            selected = pygame.surfarray.array_alpha(
                component.to_surface(
                    setcolor=(255, 255, 255, 255),
                    unsetcolor=(0, 0, 0, 0),
                )
            ) > 0
            if index != joined:
                selections.append(selected)
                continue

            # A few generated poses touch at the staff. Cut only that narrow
            # contact, keeping every other pixel with its connected figure.
            nominal = width * (index + 1) // GRID_COLUMNS
            radius = width // 16
            column_ink = (source_alpha > ALPHA_THRESHOLD).sum(axis=1)
            cut = min(
                range(nominal - radius, nominal + radius + 1),
                key=lambda x: (column_ink[x], abs(x - nominal)),
            )
            left = selected.copy()
            left[cut:, :] = False
            right = selected.copy()
            right[:cut, :] = False
            selections.extend((left, right))

        if len(selections) != GRID_COLUMNS:
            raise RuntimeError(f"boss row {row + 1}: incomplete pose separation")

        for column in range(GRID_COLUMNS):
            selected = selections[column]
            # Retain the low-alpha outline around each connected silhouette.
            outline = selected.copy()
            outline[1:, :] |= selected[:-1, :]
            outline[:-1, :] |= selected[1:, :]
            outline[:, 1:] |= selected[:, :-1]
            outline[:, :-1] |= selected[:, 1:]
            frame = region.copy()
            alpha = pygame.surfarray.pixels_alpha(frame)
            alpha[~outline] = 0
            del alpha
            bbox = opaque_bbox(frame)
            if not bbox.width or not bbox.height:
                raise RuntimeError(f"empty boss pose at row {row + 1}, column {column + 1}")
            frames.append(frame)
            metadata.append((bbox, row))

    return frames, metadata


def build_strip(prefix: str, animation: str, target_neutral_height: int):
    source_prefix = "boss" if prefix == "gundyr" else prefix
    source_path = SOURCE_DIR / f"{source_prefix}_{animation}.png"
    sheet = pygame.image.load(source_path).convert_alpha()
    # The lower-row thrusts in heavy_b extend across the upper row's cuts.
    # Find independent transparent gaps so each blade remains with its owner.
    if prefix == "gundyr" and animation in BOSS_ATTACKS:
        frames, metadata = split_connected_poses(sheet)
    else:
        frames, metadata = split_grid(
            sheet, separate_rows=prefix == "hero" and animation == "heavy_b"
        )

    # Death ends in a deliberately short lying pose. Scale from the initial
    # standing frame so the armor remains the same size as the other strips.
    if prefix == "hero" and animation == "death":
        anchor_heights = [metadata[0][0].height]
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

    prepared = []
    for frame, (bbox, _), lift in zip(frames, metadata, lifts):
        cropped = frame.subsurface(bbox).copy()
        size = (
            max(1, round(cropped.get_width() * scale)),
            max(1, round(cropped.get_height() * scale)),
        )
        prepared.append(
            (
                pygame.transform.smoothscale(cropped, size),
                round(lift * scale),
            )
        )

    if prefix == "gundyr":
        for (attack, frame_index), replacement in BOSS_FRAME_REPLACEMENTS.items():
            if animation == attack:
                prepared[frame_index] = prepared[replacement]

    cell_width = (
        max(frame.get_width() for frame, _ in prepared)
        + HORIZONTAL_PADDING * 2
    )
    cell_height = (
        max(frame.get_height() + lift for frame, lift in prepared)
        + TOP_PADDING
        + BOTTOM_PADDING
    )
    strip = pygame.Surface((cell_width * len(prepared), cell_height), pygame.SRCALPHA)
    baseline = cell_height - BOTTOM_PADDING

    for index, (frame, lift) in enumerate(prepared):
        isolated_cell = pygame.Surface((cell_width, cell_height), pygame.SRCALPHA)
        destination = (
            (cell_width - frame.get_width()) // 2,
            baseline - lift - frame.get_height(),
        )
        isolated_cell.blit(frame, destination)

        if prefix == "gundyr":
            for rect in BOSS_SHEET_BLEED.get((animation, index), ()):
                isolated_cell.fill((0, 0, 0, 0), rect)

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
        strip.blit(isolated_cell, (index * cell_width, 0))

    output_path = OUTPUT_DIR / f"{prefix}_{animation}.png"
    pygame.image.save(strip, output_path)
    print(
        f"{output_path.name}: 10 frames, cell={cell_width}x{cell_height}, "
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
