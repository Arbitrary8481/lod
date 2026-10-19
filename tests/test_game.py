import random
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "legend_of_darkness" / "app"))

from game import data as D  # noqa: E402
from game.engine import Game, max_hp, xp_for_kill, xp_needed  # noqa: E402
from game.events import EVENTS  # noqa: E402
from game.store import Store  # noqa: E402


class GameTest(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 14, 12)
        self.game = Game(Store(":memory:"), rng=random.Random(42), clock=lambda: self.now)

    def make(self, pid="u1", name="Arwen", spec="thief"):
        self.game.view(pid, name)
        self.game.act(pid, "create.name:hint")
        return self.game.act(pid, "create.spec:" + spec)

    def p(self, pid="u1"):
        return self.game.store.get_player(pid)

    def edit(self, pid="u1", **changes):
        p = self.p(pid)
        p.update(changes)
        self.game.store.save_player(p)

    def next_day(self):
        self.now += timedelta(days=1)

    def test_character_creation(self):
        screen = self.game.view("u1", "Arwen")
        self.assertIn("create.name:hint", [i["a"] for s in screen["nav"] for i in s["items"]])
        screen = self.make()
        p = self.p()
        self.assertEqual(p["name"], "Arwen")
        self.assertEqual(p["loc"], "village")
        self.assertTrue(any("new day" in line for line in screen["text"]))
        self.assertTrue(screen["stats"])

    def test_bad_and_duplicate_names(self):
        self.game.view("u1", "")
        self.game.act("u1", "create.name", "{R}<script>")
        self.assertIsNone(self.p()["name"])
        self.make("u2", "Bilbo")
        self.game.view("u3", "")
        self.game.act("u3", "create.name", "bilbo")
        self.assertIsNone(self.p("u3")["name"])

    def test_actions_not_on_screen_are_rejected(self):
        self.make()
        gold = self.p()["gold"]
        screen = self.game.act("u1", "bank.deposit:all")
        self.assertEqual(self.p()["gold"], gold)
        self.assertIn("can't do that", screen["text"][0])

    def test_forest_fight_resolves(self):
        self.make()
        self.game.act("u1", "goto:forest")
        turns = self.p()["turns"]
        for _ in range(50):
            p = self.p()
            if p["loc"] == "forest":
                self.game.act("u1", "forest.search:normal")
            elif p["loc"] == "fight":
                self.game.act("u1", "fight.attack")
            elif p["loc"] == "event":
                self.game.act("u1", p["allowed"][-1])
            if self.p()["xp"] > 0:
                break
        self.assertGreater(self.p()["xp"], 0)
        self.assertLess(self.p()["turns"], turns + 2)

    def test_death_and_new_day_resurrection(self):
        self.make()
        self.edit(hp=1, gold=500)
        self.game.act("u1", "goto:forest")
        for _ in range(200):
            p = self.p()
            if not p["alive"]:
                break
            if p["loc"] == "fight":
                self.game.act("u1", "fight.attack")
            elif p["loc"] == "event":
                self.game.act("u1", p["allowed"][-1])
            else:
                self.edit(hp=1, loc="forest")
                self.game.act("u1", "forest.search:normal")
        p = self.p()
        self.assertFalse(p["alive"])
        self.assertEqual(p["gold"], 0)
        self.assertEqual(p["loc"], "shades")
        self.assertTrue(any("slain" in n for n in self.game.store.recent_news(5)))
        self.next_day()
        self.game.view("u1")
        p = self.p()
        self.assertTrue(p["alive"])
        self.assertEqual(p["hp"], max_hp(p))
        self.assertEqual(p["loc"], "village")

    def test_shop_trade_in(self):
        self.make()
        self.edit(gold=10000)
        self.game.act("u1", "goto:weapons")
        self.game.act("u1", "weapons.buy:5")
        p = self.p()
        self.assertEqual(p["weapon"], 5)
        expected = 10000 - (D.gear_cost(5) - int(D.gear_cost(1) * 0.75))
        self.assertEqual(p["gold"], expected)

    def test_bank_and_interest(self):
        self.make()
        self.edit(gold=1000)
        self.game.act("u1", "goto:bank")
        self.game.act("u1", "bank.deposit", "400")
        self.assertEqual((self.p()["gold"], self.p()["bank"]), (600, 400))
        self.game.act("u1", "bank.withdraw", "lots")
        self.assertEqual(self.p()["bank"], 400)
        self.next_day()
        self.game.view("u1")
        self.assertEqual(self.p()["bank"], 412)

    def test_master_levels_you_up(self):
        self.make(spec="dark")
        self.edit(xp=xp_needed(1), weapon=6, armor=6)
        self.game.act("u1", "goto:training")
        self.game.act("u1", "training.challenge")
        while self.p()["loc"] == "fight":
            self.game.act("u1", "fight.attack")
        self.assertEqual(self.p()["level"], 2)
        self.assertTrue(any("level 2" in n for n in self.game.store.recent_news(3)))

    def test_master_requires_experience(self):
        self.make()
        self.game.act("u1", "goto:training")
        self.game.act("u1", "training.challenge")
        self.assertEqual(self.p()["loc"], "training")

    def test_pvp_ambush(self):
        self.make("u1", "Attacker")
        self.make("u2", "Sleeper")
        self.edit("u1", weapon=15, armor=15, level=3)
        self.edit("u2", gold=321, level=2, hp=20)
        self.game.act("u1", "goto:pvp")
        self.assertIn("pvp.attack:u2", self.p("u1")["allowed"])
        self.game.act("u1", "pvp.attack:u2")
        while self.p("u1")["loc"] == "fight":
            self.game.act("u1", "fight.attack")
        self.assertEqual(self.p("u1")["gold"], 50 + 321)
        victim = self.p("u2")
        self.assertFalse(victim["alive"])
        screen = self.game.view("u2")
        self.assertTrue(any("ambushed you" in line for line in screen["text"]))

    def test_inn_room_protects_from_pvp(self):
        self.make("u1", "Attacker")
        self.make("u2", "Sleeper")
        self.edit("u2", gold=200)
        self.game.act("u2", "goto:inn")
        self.game.act("u2", "inn.room")
        self.game.act("u1", "goto:pvp")
        self.assertNotIn("pvp.attack:u2", self.p("u1")["allowed"])

    def test_dragon_kill_resets_with_perk(self):
        self.make()
        self.edit(level=15, weapon=15, armor=15, bonus_hp=500, bonus_atk=100, gems=3,
                  gold=999, bank=5000)
        p = self.p()
        self.edit(hp=max_hp(p))
        self.game.act("u1", "goto:forest")
        self.game.act("u1", "forest.dragon")
        while self.p()["loc"] == "fight":
            self.game.act("u1", "fight.attack")
        self.assertEqual(self.p()["loc"], "dk")
        self.game.act("u1", "dk.perk:turns")
        p = self.p()
        self.assertEqual((p["level"], p["dk"], p["weapon"], p["bank"], p["gems"]),
                         (1, 1, 1, 0, 3))
        self.assertEqual(p["bonus_turns"], 1)

    def test_chatter_is_sanitised(self):
        self.make()
        self.game.act("u1", "village.say", "Hello {R}<b>world</b>")
        screen = self.game.view("u1")
        line = [t for t in screen["text"] if "Hello" in t][0]
        self.assertNotIn("<b>", line)
        self.assertNotIn("{R}H", line)

    def test_event_definitions_are_valid(self):
        known = {"gold", "gold_pct", "gems", "hp_pct", "turns", "charm", "xp", "max_hp",
                 "atk", "def", "skill", "fight", "news"}
        for key, ev in EVENTS.items():
            self.assertTrue(("outcomes" in ev) != ("choices" in ev), key)
            groups = [ev["outcomes"]] if "outcomes" in ev else [c["outcomes"] for c in ev["choices"]]
            if "choices" in ev:
                self.assertTrue(ev["intro"], key)
                self.assertFalse(ev["choices"][-1].get("cost"), key + ": last choice must be free")
            for outcomes in groups:
                for weight, effects, text in outcomes:
                    self.assertGreater(weight, 0, key)
                    self.assertTrue(text, key)
                    self.assertLessEqual(set(effects), known, key)

    def test_every_event_choice_resolves(self):
        self.make()
        for level in (1, 8, 15):
            for rich in (True, False):
                for key, ev in EVENTS.items():
                    for i in range(len(ev.get("choices", [{}]))):
                        for _ in range(8):
                            self.edit(level=level, hp=5 * level, turns=5, skill_uses=0,
                                      gold=10000 if rich else 0, gems=5 if rich else 0,
                                      alive=True, fight=None, event=None, loc="forest")
                            if "outcomes" in ev:
                                self.game.forest_event(p := self.p())
                                self.game.store.save_player(p)
                                continue
                            self.edit(loc="event", event=key)
                            self.game.view("u1")
                            self.game.act("u1", "event.choose:%d" % i)
                            p = self.p()
                            self.assertIn(p["loc"], ("forest", "fight", "event"), key)
                            self.assertGreaterEqual(p["hp"], 1, key)
                            self.assertGreaterEqual(p["gold"], 0, key)
                            self.assertGreaterEqual(p["turns"], 0, key)
                            if p["loc"] == "event":
                                self.assertFalse(rich, "%s choice %d blocked while rich" % (key, i))

    def test_event_cost_blocks_and_lets_you_choose_again(self):
        self.make()
        self.edit(gems=0, loc="event", event="fairy")
        self.game.view("u1")
        screen = self.game.act("u1", "event.choose:0")
        self.assertEqual(self.p()["loc"], "event")
        self.assertTrue(any("no gems" in line for line in screen["text"]))
        self.game.act("u1", "event.choose:1")
        self.assertEqual(self.p()["loc"], "forest")

    def test_event_paid_choice_shows_summary(self):
        self.make()
        self.edit(gold=1000, loc="event", event="caravan")
        self.game.view("u1")
        screen = self.game.act("u1", "event.choose:1")
        p = self.p()
        self.assertEqual((p["gems"], p["gold"]), (1, 1000 - 60))
        self.assertTrue(any("-60 gold" in line and "+1 gem" in line for line in screen["text"]))

    def test_event_fight_awards_bonus(self):
        self.make()
        self.edit(level=5, loc="event", event="doppelganger")
        self.game.view("u1")
        self.game.act("u1", "event.choose:0")
        p = self.p()
        self.assertEqual(p["loc"], "fight")
        self.assertEqual(p["fight"]["name"], "Your Shadow")
        self.assertEqual(p["fight"]["xp"], 3 * xp_for_kill(5))

    def test_full_health_never_rewards_healing(self):
        self.make()
        for _ in range(500):
            self.edit(level=10, hp=100, bonus_hp=0, gold=5000, gems=5, loc="forest", event=None,
                      fight=None)
            p = self.p()
            self.game.forest_event(p)
            self.assertNotIn("Drinking", " ".join(p["flash"]), "healing spring at full HP")
            if p["loc"] == "event":
                self.game.store.save_player(p)
                screen = self.game.view("u1")
                labels = [i["label"] for sec in screen["nav"] for i in sec["items"]]
                self.assertNotIn("healing draught", " ".join(labels))
                for action in self.p()["allowed"]:
                    self.edit(hp=100, bonus_hp=0, loc="event", event=p["event"], fight=None)
                    self.game.view("u1")
                    screen = self.game.act("u1", action)
                    self.assertNotRegex(" ".join(screen["text"]), r"\+\d+ HP\b", p["event"])

    def test_fairy_heals_only_when_hurt(self):
        self.make()
        outcomes = set()
        for _ in range(200):
            self.edit(hp=10, bonus_hp=0, gems=1, loc="event", event="fairy")
            self.game.view("u1")
            text = " ".join(self.game.act("u1", "event.choose:0")["text"])
            outcomes.add("close completely" in text)
        self.assertEqual(outcomes, {False})
        healed = False
        for _ in range(200):
            self.edit(hp=3, bonus_hp=0, gems=1, loc="event", event="fairy")
            self.game.view("u1")
            healed |= "close completely" in " ".join(self.game.act("u1", "event.choose:0")["text"])
        self.assertTrue(healed)

    def test_healing_draught_offered_only_when_hurt(self):
        self.make()
        self.edit(hp=10, loc="event", event="caravan")
        self.game.view("u1")
        self.assertNotIn("event.choose:0", self.p()["allowed"])
        self.edit(hp=4, loc="event", event="caravan")
        self.game.view("u1")
        self.assertIn("event.choose:0", self.p()["allowed"])

    def test_high_level_events_are_gated(self):
        self.make()
        seen = set()
        for _ in range(400):
            self.edit(level=1, loc="forest", event=None, fight=None)
            p = self.p()
            self.game.forest_event(p)
            seen.add(p["event"])
        self.assertNotIn("lady", seen)
        self.assertNotIn("hatchling", seen)

    def test_multiple_days_per_real_day(self):
        game = Game(Store(":memory:"), {"days_per_day": 4}, clock=lambda: self.now)
        self.assertEqual(game.today(), "2026-10-14 #3")


if __name__ == "__main__":
    unittest.main()
