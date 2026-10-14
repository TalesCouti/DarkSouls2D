import unittest

from main import Game


class PauseMenuTests(unittest.TestCase):
    def test_continue_option_resumes_current_fight(self):
        game = Game.__new__(Game)
        game.paused = True
        game.pause_selection = 0

        game.activate_pause_selection()

        self.assertFalse(game.paused)

    def test_return_option_restores_main_menu_and_resets_fight(self):
        game = Game.__new__(Game)
        game.menu = False
        game.menu_page = "cheats"
        game.menu_selection = 1
        game.paused = True
        game.pause_selection = 1
        game.music_ready = False
        game.cheat_health_index = Game.CHEAT_HEALTH_OPTIONS.index(500)
        game.cheat_damage_index = Game.CHEAT_DAMAGE_OPTIONS.index(5.0)

        game.activate_pause_selection()

        self.assertTrue(game.menu)
        self.assertFalse(game.paused)
        self.assertEqual(game.menu_page, "main")
        self.assertEqual(game.menu_selection, 0)
        self.assertEqual(game.hero.max_hp, 500)
        self.assertEqual(game.hero.damage_multiplier, 5.0)


if __name__ == "__main__":
    unittest.main()
