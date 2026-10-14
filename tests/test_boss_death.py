import unittest

import pygame

from main import BOSS_DEATH_DURATION, Gundyr, Hero


class BossDeathTests(unittest.TestCase):
    def test_lethal_damage_starts_and_advances_death_animation(self):
        boss = Gundyr()
        boss.state = "idle"

        boss.receive(boss.max_hp)
        boss.update(.45, Hero())

        self.assertEqual(boss.state, "dead")
        self.assertEqual(boss.hp, 0)
        self.assertAlmostEqual(boss.dead_time, .45)

    def test_boss_is_hidden_only_after_death_animation_finishes(self):
        surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
        frame = pygame.Surface((120, 180), pygame.SRCALPHA)
        frame.fill((220, 210, 190, 255))
        sprites = {"slam": [frame] * 10}
        boss = Gundyr()
        boss.state = "dead"

        boss.dead_time = BOSS_DEATH_DURATION - .1
        boss.draw(surface, sprites, pygame.Vector2())
        self.assertGreater(surface.get_bounding_rect().width, 0)

        surface.fill((0, 0, 0, 0))
        boss.dead_time = BOSS_DEATH_DURATION + .1
        boss.draw(surface, sprites, pygame.Vector2())
        self.assertEqual(surface.get_bounding_rect().width, 0)


if __name__ == "__main__":
    unittest.main()
