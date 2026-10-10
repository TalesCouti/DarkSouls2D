"""Headless checks for newly drawn, independent PNGs (no puppet animation)."""
import builtins
import contextlib
import io
import os
from pathlib import Path
from statistics import median
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import pygame
import main
import prepare_drawn_walk as exporter


class FrameRecorder(pygame.Surface):
    def blit(self, source, *args, **kwargs):
        self.last_frame = source
        return super().blit(source, *args, **kwargs)


class DrawnWalkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))
        cls.source = pygame.image.load(exporter.SOURCE).convert_alpha()
        cls.frames = main.SpriteArt._strips("gundyr", ("walk",), 1.0)["walk"]

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_sixteen_independent_files_not_sixty_artificial_frames(self):
        self.assertEqual(len(self.frames), 16)
        self.assertEqual(sorted(path.name for path in exporter.OUTPUT.glob("*.png")),
                         [f"{index:02}.png" for index in range(16)])
        self.assertEqual({frame.get_size() for frame in self.frames}, {exporter.CELL_SIZE})

    def test_complete_source_drawings_are_separate_and_not_clipped(self):
        drawings = exporter.source_drawings(self.source)
        self.assertEqual(len(drawings), 16)
        for index, (rect, silhouette) in enumerate(drawings):
            self.assertGreater(rect.left, 0)
            self.assertLess(rect.right, self.source.get_width())
            for _, other in drawings[index + 1:]:
                self.assertIsNone(silhouette.overlap(other, (0, 0)))

    def test_passing_drawings_really_lift_a_boot(self):
        def floor_contacts(frame):
            columns = [x for x in range(8, exporter.BODY_AXIS + 45)
                       if any(frame.get_at((x, y)).a > 24
                              for y in range(exporter.BASELINE - 2, exporter.BASELINE))]
            return sum(index == 0 or x > columns[index - 1] + 1
                       for index, x in enumerate(columns))

        self.assertEqual(floor_contacts(self.frames[0]), 2)
        # The selected artist-drawn passing poses are 06 and 11. Other frames
        # include toe-off/heel reach, where a second toe can approach the floor.
        for index in (5, 10):
            with self.subTest(passing=index):
                self.assertEqual(floor_contacts(self.frames[index]), 1)

    def test_every_pose_is_distinct_including_the_torso(self):
        pixels = {pygame.image.tobytes(frame, "RGBA") for frame in self.frames}
        self.assertEqual(len(pixels), 16)
        torso = pygame.Rect(exporter.BODY_AXIS - 14,
                            exporter.BASELINE - exporter.WALK_POSE_HEIGHT + 17, 38, 36)
        chest = {pygame.image.tobytes(frame.subsurface(torso), "RGBA") for frame in self.frames}
        self.assertEqual(len(chest), 16)

    def test_saved_frames_match_the_source_packing_exactly(self):
        for saved, fresh in zip(self.frames, exporter.pack_frames(self.source)):
            self.assertEqual(pygame.image.tobytes(saved, "RGBA"), pygame.image.tobytes(fresh, "RGBA"))

    def test_safe_margins_complete_weapon_and_same_support_floor(self):
        for index, frame in enumerate(self.frames):
            with self.subTest(frame=index):
                bounds = frame.get_bounding_rect(min_alpha=24)
                self.assertGreaterEqual(bounds.left, 8)
                self.assertLessEqual(bounds.right, frame.get_width() - 8)
                self.assertGreaterEqual(bounds.top, 8)
                self.assertEqual(bounds.bottom, exporter.BASELINE)
                parts = sorted(pygame.mask.from_surface(frame, 24).connected_components(),
                               key=lambda mask: mask.count(), reverse=True)
                self.assertTrue(all(part.count() <= 12 for part in parts[1:]))

    def test_pose_heights_are_not_scaled_independently(self):
        heights = [frame.get_bounding_rect(min_alpha=24).height for frame in self.frames]
        self.assertGreater(max(heights), min(heights))
        self.assertLessEqual(max(heights) - min(heights), 5)

    def test_bent_walk_is_not_enlarged_to_the_upright_idle_height(self):
        idle = main.SpriteArt._strips("gundyr", ("idle",), 1.0)["idle"]
        idle_height = median(frame.get_bounding_rect(min_alpha=24).height for frame in idle)
        # A bent torso and flexed knees must reduce pose height, not cause
        # larger helmet/plates through a full-height normalization to idle.
        for frame in self.frames:
            height = frame.get_bounding_rect(min_alpha=24).height
            self.assertGreater(height, idle_height * 0.75)
            self.assertLess(height, idle_height * 0.90)

    def test_generated_metal_palette_matches_idle_and_attacks_without_bright_silver_pop(self):
        def palette(frames):
            colors = [frame.get_at((x, y)) for frame in frames
                      for y in range(frame.get_height()) for x in range(frame.get_width())
                      if frame.get_at((x, y)).a > 200]
            luminance = sorted(.2126 * color.r + .7152 * color.g + .0722 * color.b
                               for color in colors)
            levels = [luminance[int((len(luminance) - 1) * fraction)]
                      for fraction in (.90, .95, .99)]
            warmth = median(color.r - color.b for color in colors)
            return levels, warmth

        existing = main.SpriteArt._strips("gundyr", ("idle", "sweep_a", "sweep_b"), 1.0)
        references = [palette(frames) for frames in existing.values()]
        walk, walk_warmth = palette(self.frames)
        # Different existing poses expose different areas of metal and cloth.
        # Match their observed value range, not just a single standing pose,
        # without allowing the previous pale cream/silver metal to return.
        for index, (actual, tolerance) in enumerate(zip(walk, (12, 12, 25))):
            values = [levels[index] for levels, _ in references]
            self.assertGreaterEqual(actual, min(values) - tolerance)
            self.assertLessEqual(actual, max(values) + tolerance)
        # A few RGB levels allow natural painted reflections/cloth coverage,
        # but not the noticeably warm bronze tint of the previous drawings.
        self.assertLessEqual(walk_warmth, max(warmth for _, warmth in references) + 5)

    def test_walk_has_no_heavy_black_ring_around_lit_material(self):
        def luminance(color):
            return .2126 * color.r + .7152 * color.g + .0722 * color.b

        lit_edges = ink_edges = 0
        for frame in self.frames:
            for y in range(3, frame.get_height() - 3):
                for x in range(3, frame.get_width() - 3):
                    color = frame.get_at((x, y))
                    if color.a < 128:
                        continue
                    if all(frame.get_at((x + dx, y + dy)).a >= 128
                           for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))):
                        continue
                    inside = [frame.get_at((x + dx, y + dy))
                              for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2))]
                    brightest = max((luminance(pixel) for pixel in inside if pixel.a > 200),
                                    default=0)
                    if brightest < 70:
                        continue  # Dark cloth/shadow is not an unwanted ink stroke.
                    lit_edges += 1
                    value = luminance(color)
                    ink_edges += value < 36 and value < brightest * .5
        # The outlined source had ~19% dark rings beside lit material; the
        # repainted source has <1%. Leave room for small natural contact shadows.
        self.assertGreater(lit_edges, 500)
        self.assertLess(ink_edges / lit_edges, .06)

    def test_corrected_source_has_wide_vertical_gutters_between_rows(self):
        bounds = exporter.source_rects(self.source)
        for row in range(3):
            lowest = max(rect.bottom for rect in bounds[row * 4:row * 4 + 4])
            next_top = min(rect.top for rect in bounds[(row + 1) * 4:(row + 2) * 4])
            self.assertGreaterEqual(next_top - lowest, 32)

    def test_export_never_imports_warping_or_interpolation_tools(self):
        original_import = builtins.__import__

        def guarded_import(name, *args, **kwargs):
            if name.split(".")[0] in ("numpy", "cv2", "rig_gundyr_walk", "interpolate_walk"):
                raise AssertionError(f"Drawn export must not import {name}")
            return original_import(name, *args, **kwargs)

        with tempfile.TemporaryDirectory() as directory:
            with patch("builtins.__import__", guarded_import), contextlib.redirect_stdout(io.StringIO()):
                frames = exporter.export_walk(Path(directory))
            self.assertEqual(len(frames), 16)
            self.assertEqual(len(list(Path(directory).glob("*.png"))), 16)

    def test_normal_reexport_cannot_restore_the_old_rig(self):
        import prepare_independent_sprites as previous_exporter
        with patch.object(exporter, "export_walk") as draw_export:
            previous_exporter.build_strip("gundyr", "walk", 104)
        draw_export.assert_called_once_with()

    def test_changed_source_size_and_missing_drawings_are_rejected(self):
        with self.assertRaises(ValueError):
            exporter.source_rects(pygame.Surface((320, 320), pygame.SRCALPHA))
        with self.assertRaises(ValueError):
            exporter.source_rects(pygame.Surface(exporter.SOURCE_SIZE, pygame.SRCALPHA))

    def test_runtime_loads_individual_pngs_not_the_old_strip(self):
        original_load = pygame.image.load
        loaded = []

        def record(path):
            loaded.append(Path(path))
            return original_load(path)

        with patch("pygame.image.load", record):
            frames = main.SpriteArt._strips("gundyr", ("walk",), 1.0)["walk"]
        self.assertEqual(len(frames), 16)
        self.assertEqual({path.parent for path in loaded}, {exporter.OUTPUT})

    def test_missing_extra_or_differently_sized_png_is_rejected(self):
        for issue in ("missing", "extra", "wrong_size"):
            with self.subTest(issue=issue), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                folder = root / "assets" / "animations_v6" / "gundyr_walk"
                folder.mkdir(parents=True)
                for index in range(16):
                    if issue == "missing" and index == 8:
                        continue
                    size = (45, 50) if issue == "wrong_size" and index == 8 else (40, 50)
                    pygame.image.save(pygame.Surface(size, pygame.SRCALPHA), folder / f"{index:02}.png")
                if issue == "extra":
                    pygame.image.save(self.frames[0], folder / "16.png")
                with patch.object(main, "ROOT", root), self.assertRaises(pygame.error):
                    main.SpriteArt._strips("gundyr", ("walk",), 1.0)

    def test_full_cycle_has_sixteen_real_poses_in_order(self):
        boss = main.Gundyr()
        boss.state, boss.moving, boss.facing = "idle", True, 1
        surface = FrameRecorder((main.WIDTH, main.HEIGHT))
        for index in range(32):
            boss.walk_timer = (index + 0.5) / 16 * main.GUNDYR_WALK_CYCLE_DURATION
            boss.draw(surface, {"walk": self.frames}, pygame.Vector2())
            self.assertIs(surface.last_frame, self.frames[index % 16])
        self.assertEqual(main.GUNDYR_WALK_CYCLE_DURATION, 1.6)

    def test_both_directions_keep_the_boots_on_the_floor(self):
        frames = main.SpriteArt._strips("gundyr", ("walk",), 1.55)["walk"]
        for frame in frames:
            for facing in (1, -1):
                sprite = pygame.transform.flip(frame, facing < 0, False)
                destination = sprite.get_rect(midbottom=(600, main.GROUND + 4))
                feet = sprite.get_bounding_rect(min_alpha=24).move(destination.topleft)
                self.assertLessEqual(abs(feet.bottom - (main.GROUND + 1)), 1)

    def test_walking_phase_pauses_and_resumes(self):
        boss, hero = main.Gundyr(), main.Hero()
        boss.state, boss.cooldown, boss.walk_timer = "idle", 100, 0.42
        hero.pos.x = boss.pos.x - 150
        boss.update(0.02, hero)
        self.assertFalse(boss.moving)
        self.assertAlmostEqual(boss.walk_timer, 0.42)
        hero.pos.x = boss.pos.x - 400
        boss.update(0.02, hero)
        self.assertTrue(boss.moving)
        self.assertAlmostEqual(boss.walk_timer, 0.44)
        boss.state, boss.timer = "sweep", 0
        boss.update(0.02, hero)
        self.assertAlmostEqual(boss.walk_timer, 0.44)

    def test_cadence_follows_actual_travel_and_retreat(self):
        boss, hero = main.Gundyr(), main.Hero()
        boss.state, boss.cooldown, boss.phase = "idle", 100, 2
        hero.pos.x = boss.pos.x - 400
        boss.update(0.1, hero)
        self.assertAlmostEqual(boss.walk_timer, 10.2 / main.GUNDYR_WALK_REFERENCE_SPEED)
        previous = boss.walk_timer
        hero.pos.x = boss.pos.x - 80
        boss.update(0.1, hero)
        self.assertAlmostEqual(boss.walk_timer, previous - 4.4 / main.GUNDYR_WALK_REFERENCE_SPEED)

    def test_retreat_wraps_to_last_pose_without_resetting(self):
        boss = main.Gundyr()
        boss.state, boss.moving, boss.facing = "idle", True, 1
        boss.walk_timer = -main.GUNDYR_WALK_CYCLE_DURATION / 32
        surface = FrameRecorder((main.WIDTH, main.HEIGHT))
        boss.draw(surface, {"walk": self.frames}, pygame.Vector2())
        self.assertIs(surface.last_frame, self.frames[-1])

    def test_v5_and_v3_strip_fallbacks_keep_their_original_counts(self):
        for version, count in (("animations_v5", 60), ("animations_v3", 10)):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                folder = root / "assets" / version
                folder.mkdir(parents=True)
                pygame.image.save(pygame.Surface((count * 20, 30), pygame.SRCALPHA), folder / "gundyr_walk.png")
                with patch.object(main, "ROOT", root):
                    frames = main.SpriteArt._strips("gundyr", ("walk",), 1.0)["walk"]
                self.assertEqual(len(frames), count)

    def test_bad_strip_width_is_rejected_instead_of_bleeding(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root / "assets" / "animations_v5"
            folder.mkdir(parents=True)
            pygame.image.save(pygame.Surface((121, 30), pygame.SRCALPHA), folder / "gundyr_walk.png")
            with patch.object(main, "ROOT", root), self.assertRaises(pygame.error):
                main.SpriteArt._strips("gundyr", ("walk",), 1.0)


if __name__ == "__main__":
    unittest.main()
