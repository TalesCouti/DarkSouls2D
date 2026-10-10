"""Headless regression tests for Gundyr's walk assets and playback."""

import contextlib
import importlib.util
import io
import math
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

import main
from interpolate_walk import WALK_INBETWEENS, interpolate_walk_cells
from rig_gundyr_walk import (
    FOOT_CLEARANCE, LEG_RIGS, SHIN_LENGTH, THIGH_LENGTH,
    foot_pose, knee_joint,
)


class WalkGaitTests(unittest.TestCase):
    def test_one_foot_always_supports_the_body_and_both_feet_take_turns(self):
        support_counts = [0, 0]
        maximum_lift = [0.0, 0.0]
        for index in range(1000):
            supports = []
            for leg_index, rig in enumerate(LEG_RIGS):
                ankle, angle, supported = foot_pose(
                    index / 1000 + rig["phase_offset"], rig["front_x"], 111,
                )
                supports.append(supported)
                support_counts[leg_index] += supported
                maximum_lift[leg_index] = max(maximum_lift[leg_index], 111 - ankle[1])
                if supported:
                    self.assertEqual(ankle[1], 111)
                    self.assertEqual(angle, 0)
            self.assertTrue(any(supports))
        self.assertTrue(all(500 <= count <= 560 for count in support_counts))
        self.assertTrue(all(lift >= FOOT_CLEARANCE - 0.01 for lift in maximum_lift))

    def test_knees_bend_without_changing_limb_lengths(self):
        for index in range(1000):
            phase = index / 1000
            for rig in LEG_RIGS:
                ankle, _, _ = foot_pose(phase + rig["phase_offset"], rig["front_x"], 111)
                hip = (rig["target_hip"][0], rig["target_hip"][1] + 1.5 * math.sin(4 * math.pi * phase))
                knee = knee_joint(hip, ankle)
                self.assertAlmostEqual(math.dist(hip, knee), THIGH_LENGTH)
                self.assertAlmostEqual(math.dist(knee, ankle), SHIN_LENGTH)
                self.assertGreater(knee[0], min(hip[0], ankle[0]))

    def test_foot_trajectory_loops_without_a_position_jump(self):
        for rig in LEG_RIGS:
            start, _, _ = foot_pose(0, rig["front_x"], 111)
            end, angle, _ = foot_pose(1 - 1e-8, rig["front_x"], 111)
            self.assertLess(math.dist(start, end), 1e-5)
            self.assertLess(abs(angle), 1e-5)


class WalkPlaybackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))
        cls.frames = main.SpriteArt._strips("gundyr", ("walk",), 1.0)["walk"]

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_sixty_isolated_frames_with_safe_borders_and_grounded_feet(self):
        self.assertEqual(len(self.frames), 60)
        self.assertEqual(len({frame.get_size() for frame in self.frames}), 1)
        for index, frame in enumerate(self.frames):
            with self.subTest(frame=index):
                bounds = frame.get_bounding_rect(min_alpha=24)
                self.assertGreaterEqual(bounds.left, 8)
                self.assertLessEqual(bounds.right, frame.get_width() - 8)
                self.assertGreaterEqual(bounds.top, 8)
                self.assertEqual(bounds.bottom, frame.get_height() - 2)
                # No detached blade or mirrored axe-sized component.
                components = sorted(
                    pygame.mask.from_surface(frame, 24).connected_components(),
                    key=lambda component: component.count(), reverse=True,
                )
                self.assertTrue(all(part.count() <= 12 for part in components[1:]))

    def test_same_cycle_duration_with_more_frames(self):
        boss = main.Gundyr()
        boss.state, boss.moving, boss.facing = "idle", True, 1

        class FrameRecorder(pygame.Surface):
            def blit(self, source, *args, **kwargs):
                self.last_frame = source
                return super().blit(source, *args, **kwargs)

        surface = FrameRecorder((main.WIDTH, main.HEIGHT))
        # Probe the middle of each interval through the actual draw method.
        for index in range(len(self.frames) * 2):
            boss.walk_timer = (
                (index + 0.5) / len(self.frames) * main.GUNDYR_WALK_CYCLE_DURATION
            )
            boss.draw(surface, {"walk": self.frames}, pygame.Vector2())
            self.assertIs(surface.last_frame, self.frames[index % 60])
        self.assertAlmostEqual(main.GUNDYR_WALK_CYCLE_DURATION, 1.6666666667)

    def test_baked_passing_poses_lift_a_boot_off_the_floor(self):
        def floor_contacts(frame):
            occupied_columns = [
                x for x in range(15, 115)
                if any(frame.get_at((x, y)).a > 24 for y in range(117, 120))
            ]
            return sum(
                index == 0 or x > occupied_columns[index - 1] + 1
                for index, x in enumerate(occupied_columns)
            )

        # Contact has two boots on the floor. Passing has only the supporting
        # boot; the opposite knee/boot is visibly raised in the actual PNG.
        self.assertEqual(floor_contacts(self.frames[0]), 2)
        self.assertEqual(floor_contacts(self.frames[30]), 2)
        self.assertEqual(floor_contacts(self.frames[15]), 1)
        self.assertEqual(floor_contacts(self.frames[45]), 1)

    def test_halberd_blade_stays_identical_at_matching_body_heights(self):
        blade = pygame.Rect(110, 83, 40, 30)
        reference = pygame.image.tobytes(self.frames[0].subsurface(blade), "RGBA")
        for index in (15, 30, 45):
            self.assertEqual(
                pygame.image.tobytes(self.frames[index].subsurface(blade), "RGBA"),
                reference,
            )

    def test_scaled_boots_share_the_same_floor_in_both_directions(self):
        frames = main.SpriteArt._strips("gundyr", ("walk",), 1.55)["walk"]
        for frame in frames:
            for facing in (1, -1):
                sprite = pygame.transform.flip(frame, facing < 0, False)
                destination = sprite.get_rect(midbottom=(600, main.GROUND + 4))
                feet = sprite.get_bounding_rect(min_alpha=24).move(destination.topleft)
                self.assertEqual(feet.bottom, main.GROUND + 1)

    def test_walking_phase_pauses_and_resumes(self):
        boss, hero = main.Gundyr(), main.Hero()
        boss.state, boss.cooldown = "idle", 100
        boss.walk_timer = 0.42
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

    def test_legacy_walk_still_uses_ten_frames(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy = root / "assets" / "animations_v3"
            legacy.mkdir(parents=True)
            strip = pygame.Surface((200, 30), pygame.SRCALPHA)
            pygame.image.save(strip, legacy / "gundyr_walk.png")
            with patch.object(main, "ROOT", root):
                frames = main.SpriteArt._strips("gundyr", ("walk",), 1.0)["walk"]
            self.assertEqual(len(frames), 10)
            self.assertEqual(frames[0].get_size(), (20, 30))

    def test_bad_strip_width_is_rejected_instead_of_bleeding(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            independent = root / "assets" / "animations_v5"
            independent.mkdir(parents=True)
            pygame.image.save(
                pygame.Surface((121, 30), pygame.SRCALPHA),
                independent / "gundyr_walk.png",
            )
            with patch.object(main, "ROOT", root):
                with self.assertRaises(pygame.error):
                    main.SpriteArt._strips("gundyr", ("walk",), 1.0)


@unittest.skipUnless(
    importlib.util.find_spec("cv2") and importlib.util.find_spec("numpy"),
    "Install requirements-assets.txt to test offline interpolation",
)
class WalkExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import prepare_independent_sprites as exporter

        pygame.init()
        pygame.display.set_mode((1, 1))
        cls.base = []

        def capture(cells):
            cls.base = [cell.copy() for cell in cells]
            return cells

        # Reconstruct the 20 articulated key poses from the clean source armor.
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(exporter, "OUTPUT_DIR", Path(directory)):
                with patch("interpolate_walk.interpolate_walk_cells", capture):
                    with contextlib.redirect_stdout(io.StringIO()):
                        exporter.build_strip("gundyr", "walk", 104)
        cls.generated = interpolate_walk_cells(cls.base)

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_articulated_key_poses_are_copied_unchanged(self):
        self.assertEqual(len(self.generated), len(self.base) * (WALK_INBETWEENS + 1))
        for before, after in zip(self.base, self.generated[::WALK_INBETWEENS + 1]):
            self.assertEqual(
                pygame.image.tobytes(before, "RGBA"),
                pygame.image.tobytes(after, "RGBA"),
            )

    def test_transitions_contain_new_geometry_not_repeated_frames(self):
        import numpy as np

        for index, start in enumerate(self.base):
            end = self.base[(index + 1) % len(self.base)]
            start_rgba = pygame.image.tobytes(start, "RGBA")
            end_rgba = pygame.image.tobytes(end, "RGBA")
            for step in range(1, WALK_INBETWEENS + 1):
                middle = self.generated[index * 3 + step]
                middle_rgba = pygame.image.tobytes(middle, "RGBA")
                if start_rgba == end_rgba:
                    self.assertEqual(middle_rgba, start_rgba)
                    continue
                self.assertNotEqual(middle_rgba, start_rgba)
                self.assertNotEqual(middle_rgba, end_rgba)
                a = pygame.surfarray.array_alpha(start).astype(float)
                b = pygame.surfarray.array_alpha(end).astype(float)
                alpha = pygame.surfarray.array_alpha(middle).astype(float)
                t = step / 3
                self.assertFalse(np.allclose(alpha, (1 - t) * a + t * b))

    def test_adjacent_changes_are_smaller_including_the_loop(self):
        import numpy as np

        def changes(frames):
            images = [
                pygame.surfarray.array3d(frame).astype(float)
                * (pygame.surfarray.array_alpha(frame)[..., None] / 255)
                for frame in frames
            ]
            return [
                np.abs(image - images[(index + 1) % len(images)]).mean()
                for index, image in enumerate(images)
            ]

        original, smooth = changes(self.base), changes(self.generated)
        self.assertLess(np.mean(smooth), np.mean(original) * 0.6)
        self.assertLess(max(smooth), max(original) * 0.6)
        self.assertLess(smooth[-1], original[-1])

    def test_upper_body_anchor_does_not_wobble(self):
        from prepare_independent_sprites import opaque_bbox, upper_body_anchor_x

        anchors = []
        for frame in self.generated:
            bounds = opaque_bbox(frame)
            anchors.append(bounds.left + upper_body_anchor_x(frame, bounds))
        self.assertLessEqual(max(anchors) - min(anchors), 1)

    def test_empty_input_and_mismatched_cells(self):
        self.assertEqual(interpolate_walk_cells([]), [])
        with self.assertRaises(ValueError):
            interpolate_walk_cells([
                pygame.Surface((20, 20), pygame.SRCALPHA),
                pygame.Surface((21, 20), pygame.SRCALPHA),
            ])


if __name__ == "__main__":
    unittest.main()
