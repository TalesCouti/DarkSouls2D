import unittest

from main import Game, Hero


class CheatSettingsTests(unittest.TestCase):
    def test_custom_health_is_applied_to_new_hero(self):
        hero = Hero(max_hp=500)

        self.assertEqual(hero.hp, 500)
        self.assertEqual(hero.max_hp, 500)

    def test_damage_multiplier_applies_to_light_and_heavy_attacks(self):
        hero = Hero(damage_multiplier=5)

        hero.state = "attack"
        hero.timer = .3
        hero.combo = 1
        _, light_damage = hero.attack_box()

        hero.state = "heavy"
        hero.timer = .6
        hero.attack_variant = "heavy_a"
        _, heavy_damage = hero.attack_box()

        self.assertEqual(light_damage, 85)
        self.assertEqual(heavy_damage, 155)

    def test_restart_applies_selected_cheat_values(self):
        game = Game.__new__(Game)
        game.menu = True
        game.cheat_health_index = Game.CHEAT_HEALTH_OPTIONS.index(500)
        game.cheat_damage_index = Game.CHEAT_DAMAGE_OPTIONS.index(10.0)

        game.restart()

        self.assertEqual(game.hero.max_hp, 500)
        self.assertEqual(game.hero.damage_multiplier, 10.0)


if __name__ == "__main__":
    unittest.main()
