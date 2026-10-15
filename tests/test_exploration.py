import unittest

from main import (
    BONFIRE_X,
    BOSS_ARENA_LEFT,
    BOSS_SPAWN_X,
    FOG_ENTER_DURATION,
    GROUND,
    HOLLOW_SPAWNS,
    Game,
    Hero,
    Hollow,
)


class ExplorationFlowTests(unittest.TestCase):
    def make_game(self):
        game = Game.__new__(Game)
        game.menu = False
        game.music_ready = False
        game.cheat_health_index = Game.CHEAT_HEALTH_OPTIONS.index(110)
        game.cheat_damage_index = Game.CHEAT_DAMAGE_OPTIONS.index(1.0)
        game.restart()
        return game

    def test_restart_begins_at_bonfire_with_five_hollows(self):
        game = self.make_game()

        self.assertEqual(game.area, "explore")
        self.assertEqual(game.hero.pos.y, GROUND)
        self.assertLess(abs(game.hero.pos.x - BONFIRE_X), 120)
        self.assertEqual([enemy.spawn_x for enemy in game.hollows], list(HOLLOW_SPAWNS))
        self.assertTrue(game.hollows[-1].strong)

    def test_rest_restores_resources_and_respawns_enemies(self):
        game = self.make_game()
        old_hollows = game.hollows
        game.hero.hp = 1
        game.hero.stamina = 2
        game.hero.flasks = 0
        game.burst = lambda *args, **kwargs: None

        game.rest_at_bonfire()

        self.assertEqual(game.hero.hp, game.hero.max_hp)
        self.assertEqual(game.hero.stamina, game.hero.max_stamina)
        self.assertEqual(game.hero.flasks, 3)
        self.assertIsNot(game.hollows[0], old_hollows[0])

    def test_fog_transition_places_combatants_in_boss_arena(self):
        game = self.make_game()
        game.start_music = lambda: None
        game.fog_transition = FOG_ENTER_DURATION

        game.enter_boss_arena()

        self.assertEqual(game.area, "boss")
        self.assertEqual(game.camera_x, BOSS_ARENA_LEFT)
        self.assertEqual(game.boss.pos.x, BOSS_SPAWN_X)
        self.assertGreater(game.hero.pos.x, BOSS_ARENA_LEFT)

    def test_hollow_slash_is_active_only_during_frames_five_to_seven(self):
        hollow = Hollow(700)
        hollow.state = "attack"

        hollow.timer = .4
        self.assertIsNone(hollow.attack_box())
        hollow.timer = .7
        self.assertIsNotNone(hollow.attack_box())
        hollow.timer = .95
        self.assertIsNone(hollow.attack_box())

    def test_parry_staggers_a_hollow(self):
        hollow = Hollow(700)
        hero = Hero()
        hero.pos.x = 650
        hero.state = "parry"
        hero.timer = .14
        hollow.state = "attack"
        hollow.timer = .7

        result = hollow.update(0, hero, [hollow])

        self.assertEqual(result, "parry")
        self.assertEqual(hollow.state, "stagger")


if __name__ == "__main__":
    unittest.main()
