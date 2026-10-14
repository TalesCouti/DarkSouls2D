"""Regression checks for the knight's wide thrust animation."""

import os
import unittest

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame

from prepare_independent_sprites import (
    ALPHA_THRESHOLD,
    BOSS_ATTACKS,
    OUTPUT_DIR,
    SAFETY_MARGIN,
    SOURCE_DIR,
    opaque_bbox,
    split_grid,
)


def visible_fragments(frame):
    mask = pygame.mask.from_surface(frame, ALPHA_THRESHOLD)
    return [
        rect
        for rect in mask.get_bounding_rects()
        if rect.width >= 4 and rect.height >= 3
    ]


class SpriteSlicingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1), flags=pygame.HIDDEN)

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_wide_thrusts_stay_in_their_source_frames(self):
        sheet = pygame.image.load(SOURCE_DIR / "hero_heavy_b.png").convert_alpha()
        frames, _ = split_grid(sheet, separate_rows=True)

        self.assertEqual(len(frames), 10)
        for index in range(5, 9):
            with self.subTest(frame=index + 1):
                self.assertEqual(len(visible_fragments(frames[index])), 1)

    def test_exported_frames_have_complete_silhouettes_and_safe_borders(self):
        strip = pygame.image.load(OUTPUT_DIR / "hero_heavy_b.png").convert_alpha()
        self.assertEqual(strip.get_width() % 10, 0)
        cell_width = strip.get_width() // 10

        for index in range(10):
            with self.subTest(frame=index + 1):
                frame = strip.subsurface((index * cell_width, 0, cell_width, strip.get_height()))
                self.assertEqual(len(visible_fragments(frame)), 1)
                bounds = opaque_bbox(frame)
                self.assertGreaterEqual(bounds.left, SAFETY_MARGIN)
                self.assertLessEqual(bounds.right, cell_width - SAFETY_MARGIN)

    def test_boss_attack_frames_keep_one_complete_figure_per_cell(self):
        for animation in BOSS_ATTACKS:
            with self.subTest(animation=animation):
                strip = pygame.image.load(
                    OUTPUT_DIR / f"gundyr_{animation}.png"
                ).convert_alpha()
                self.assertEqual(strip.get_width() % 10, 0)
                cell_width = strip.get_width() // 10
                distinct_frames = set()

                for index in range(10):
                    with self.subTest(animation=animation, frame=index + 1):
                        frame = strip.subsurface(
                            (index * cell_width, 0, cell_width, strip.get_height())
                        )
                        mask = pygame.mask.from_surface(frame, ALPHA_THRESHOLD)
                        self.assertEqual(len(mask.connected_components(20)), 1)
                        bounds = opaque_bbox(frame)
                        self.assertGreaterEqual(bounds.left, SAFETY_MARGIN)
                        self.assertLessEqual(bounds.right, cell_width - SAFETY_MARGIN)
                        distinct_frames.add(pygame.image.tobytes(frame, "RGBA"))

                self.assertGreaterEqual(len(distinct_frames), 7)


if __name__ == "__main__":
    unittest.main()
