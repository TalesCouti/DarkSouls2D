"""Split generated sprite sheets into clean, isolated animation strips."""

from pathlib import Path

import pygame


ROOT = Path(__file__).parent
SOURCE_DIR = ROOT / "assets"
OUTPUT_DIR = SOURCE_DIR / "animations_v3"
SHEETS = {
    "hero": (
        SOURCE_DIR / "hero_v3_atlas.png",
        ("idle", "walk", "dodge", "block", "attack_a", "attack_b", "heavy_a", "heavy_b"),
    ),
    "gundyr": (
        SOURCE_DIR / "gundyr_v3_atlas.png",
        ("idle", "walk", "sweep_a", "sweep_b", "thrust_a", "thrust_b", "slam", "special"),
    ),
}


def isolate_main_component(frame):
    """Remove disconnected pixels leaking in from neighbouring cells."""
    alpha_mask = pygame.mask.from_surface(frame, 24)
    components = alpha_mask.connected_components(3)
    if not components:
        return frame

    center_x = frame.get_width() / 2

    def score(component):
        rects = component.get_bounding_rects()
        if not rects:
            return -1
        rect = rects[0]
        center_penalty = abs(rect.centerx - center_x) * 4
        edge_penalty = 800 if rect.right < frame.get_width() * .12 or rect.left > frame.get_width() * .88 else 0
        return component.count() - center_penalty - edge_penalty

    main = max(components, key=score)
    keep = main.copy()

    alpha = keep.to_surface(
        setcolor=pygame.Color(255, 255, 255, 255),
        unsetcolor=pygame.Color(0, 0, 0, 0),
    )
    clean = frame.copy()
    clean.blit(alpha, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    return clean


def split_sheet(prefix, source_path, animation_names):
    sheet = pygame.image.load(source_path).convert_alpha()
    columns, rows = 10, 8
    cell_height = sheet.get_height() // rows
    offset_y = (sheet.get_height() - cell_height * rows) // 2

    calibration_row = sheet.subsurface((0, offset_y, sheet.get_width(), cell_height))
    calibration_components = [
        component
        for component in pygame.mask.from_surface(calibration_row, 24).connected_components(1000)
        if component.get_bounding_rects()
    ]
    calibration_components = sorted(
        sorted(calibration_components, key=lambda component: component.count(), reverse=True)[:columns],
        key=lambda component: component.get_bounding_rects()[0].centerx,
    )
    if len(calibration_components) != columns:
        raise RuntimeError(f"{prefix}: expected {columns} calibration poses, found {len(calibration_components)}")
    centers = [component.get_bounding_rects()[0].centerx for component in calibration_components]
    boundaries = [0]
    boundaries.extend((centers[index] + centers[index + 1]) // 2 for index in range(columns - 1))
    boundaries.append(sheet.get_width())

    horizontal_padding = 48
    output_cell_width = max(
        boundaries[index + 1] - boundaries[index] for index in range(columns)
    ) + horizontal_padding * 2
    target_baseline = cell_height - 2
    for row, animation in enumerate(animation_names):
        strip = pygame.Surface((output_cell_width * columns, cell_height), pygame.SRCALPHA)
        for column in range(columns):
            left, right = boundaries[column], boundaries[column + 1]
            rect = pygame.Rect(
                left,
                offset_y + row * cell_height,
                right - left,
                cell_height,
            )
            frame = isolate_main_component(sheet.subsurface(rect).copy())
            frame_mask = pygame.mask.from_surface(frame, 24)
            frame_rects = frame_mask.get_bounding_rects()
            if not frame_rects:
                continue
            if row <= 3:
                anchor_x = frame_rects[0].centerx
            else:
                anchor_x = centers[column] - left
            destination_x = (
                output_cell_width // 2 - anchor_x
            )
            destination_y = target_baseline - frame_rects[0].bottom
            # Compose inside an isolated cell first. Blitting directly onto
            # the full strip allowed wide swords/halberds to spill into the
            # neighbouring frame and appear wrapped on its opposite edge.
            isolated_cell = pygame.Surface(
                (output_cell_width, cell_height),
                pygame.SRCALPHA,
            )
            isolated_cell.blit(frame, (destination_x, destination_y))
            strip.blit(isolated_cell, (column * output_cell_width, 0))
        pygame.image.save(strip, OUTPUT_DIR / f"{prefix}_{animation}.png")


def main():
    pygame.init()
    pygame.display.set_mode((1, 1), flags=pygame.HIDDEN)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for prefix, (source, names) in SHEETS.items():
        split_sheet(prefix, source, names)
    print(f"Animation strips saved to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
