import hashlib
import random
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "legend_of_darkness" / "app"))

from game import data as D  # noqa: E402
from game.engine import Game, max_hp, xp_for_kill, xp_needed  # noqa: E402
from game.admin import ADMIN_HASH, check_password  # noqa: E402
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

    def test_shop_separates_upgrades_and_downgrades(self):
        self.make()
        self.edit(weapon=5, gold=500)
        screen = self.game.act("u1", "goto:weapons")
        sections = {sec["h"]: sec["items"] for sec in screen["nav"]}
        ups, downs = sections["Upgrades"], sections["Downgrades"]
        self.assertEqual([i["a"] for i in ups][:2], ["weapons.buy:6", "weapons.buy:7"])
        self.assertEqual([i["a"] for i in downs], ["weapons.buy:%d" % t for t in (4, 3, 2, 1)])
        self.assertIn("\u25b2+1", ups[0]["label"])
        self.assertIn("\u25bc-1", downs[0]["label"])
        net = D.gear_cost(6) - int(D.gear_cost(5) * 0.75)
        self.assertIn("{:,}g".format(net), ups[0]["label"])
        self.assertTrue(any("can't afford an upgrade yet" in line for line in screen["text"]))
        self.edit(gold=3000)
        screen = self.game.act("u1", "goto:weapons")
        best = [line for line in screen["text"] if "Best upgrade you can afford" in line][0]
        self.assertIn(D.WEAPONS[7], best)  # tier 7 costs under 3,000 after trade-in; tier 8 doesn't
        self.assertTrue(all("prompt" in i for i in downs))
        self.assertFalse(any("prompt" in i for i in ups))

    def test_shop_downgrade_needs_confirmation(self):
        self.make()
        self.edit(weapon=5, gold=0)
        self.game.act("u1", "goto:weapons")
        self.game.act("u1", "weapons.buy:2", "no")
        self.assertEqual(self.p()["weapon"], 5)
        screen = self.game.act("u1", "weapons.buy:2", "yes")
        p = self.p()
        self.assertEqual(p["weapon"], 2)
        self.assertEqual(p["gold"], int(D.gear_cost(5) * 0.75) - D.gear_cost(2))
        self.assertTrue(any("from 6 to {r}3" in line for line in screen["text"]))

    def test_shop_at_best_gear_has_no_upgrades(self):
        self.make()
        self.edit(armor=15)
        screen = self.game.act("u1", "goto:armor")
        self.assertNotIn("Upgrades", [sec["h"] for sec in screen["nav"] if sec["items"]])
        self.assertTrue(any("finest armour" in line for line in screen["text"]))

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

    # ---------------------------------------------------------- high/low

    def deal(self, *ranks):
        """Stack the next shuffled deck so cards come out with these ranks, in order."""
        def stack(deck):
            rest = list(deck)
            top = []
            for rank in ranks:
                card = next(c for c in rest if c // 4 + 1 == rank)
                rest.remove(card)
                top.append(card)
            deck[:] = rest + top[::-1]  # cards are drawn from the end
        self.game.rng.shuffle = stack

    def sit_at_cards(self, gold=1000):
        self.make()
        self.edit(gold=gold, level=2)
        self.game.act("u1", "goto:inn")
        self.assertIn("goto:cards", self.p()["allowed"])
        self.game.act("u1", "goto:cards")

    def test_cards_win_streak_and_cash_out(self):
        self.sit_at_cards()
        self.deal(5, 9, 3)
        self.game.act("u1", "cards.bet:25")  # 25 x level 2 = 50
        self.assertEqual(self.p()["gold"], 950)
        self.assertEqual(self.p()["cards"]["card"], 5)
        # 51 cards left, 32 of them (Six-King) beat a Five
        self.game.act("u1", "cards.guess:high")
        pot = int(50 * round(0.92 * 51 / 32, 2))
        self.assertEqual(self.p()["cards"]["pot"], pot)
        # 50 cards left, 31 of them (Ace-Eight minus the Five) are under a Nine
        self.game.act("u1", "cards.guess:low")
        pot = int(pot * round(0.92 * 50 / 31, 2))
        self.assertEqual(self.p()["cards"]["streak"], 2)
        screen = self.game.act("u1", "cards.cash")
        self.assertEqual(self.p()["gold"], 950 + pot)
        self.assertIsNone(self.p()["cards"])
        self.assertTrue(any("scoop up %d gold" % pot in line for line in screen["text"]))

    def test_cards_loss_and_tie_lose_the_pot(self):
        self.sit_at_cards()
        self.deal(7, 4)
        self.game.act("u1", "cards.bet:10")
        self.game.act("u1", "cards.guess:high")
        self.assertEqual((self.p()["gold"], self.p()["cards"]), (980, None))
        self.deal(7, 7)
        self.game.act("u1", "cards.bet:10")
        screen = self.game.act("u1", "cards.guess:low")
        self.assertEqual((self.p()["gold"], self.p()["cards"]), (960, None))
        self.assertTrue(any("A match!" in line for line in screen["text"]))

    def test_cards_impossible_guesses_are_hidden(self):
        self.sit_at_cards()
        self.deal(13)
        self.game.act("u1", "cards.bet:10")
        allowed = self.p()["allowed"]
        self.assertNotIn("cards.guess:high", allowed)
        self.assertIn("cards.guess:low", allowed)
        self.assertNotIn("goto:inn", allowed)  # must finish the hand first
        self.edit(cards=dict(self.p()["cards"], card=1))
        self.game.view("u1")
        self.assertNotIn("cards.guess:low", self.p()["allowed"])

    def test_cards_bet_limits(self):
        self.sit_at_cards(gold=30)
        screen = self.game.act("u1", "cards.bet:custom", "500")
        self.assertIn("House limit", " ".join(screen["text"]))
        screen = self.game.act("u1", "cards.bet:25")  # 50 gold, only 30 on hand
        self.assertIn("kind of coin", " ".join(screen["text"]))
        self.game.act("u1", "cards.bet:custom", "abc")
        self.game.act("u1", "cards.bet:custom", "-5")
        self.assertEqual((self.p()["gold"], self.p().get("cards")), (30, None))
        self.game.act("u1", "cards.bet:custom", "30")
        self.assertEqual((self.p()["gold"], self.p()["cards"]["pot"]), (0, 30))

    def test_cards_pot_is_capped_and_paid_out(self):
        self.sit_at_cards()
        self.deal(2, 1, 2, 1)  # long shot, safe bet, long shot again
        self.game.act("u1", "cards.bet:10")  # 20 gold
        self.game.act("u1", "cards.guess:low")  # 4 Aces in 51 cards
        self.assertEqual(self.p()["cards"]["pot"], int(20 * round(0.92 * 51 / 4, 2)))
        self.game.act("u1", "cards.guess:high")
        screen = self.game.act("u1", "cards.guess:low")
        self.assertIn("house limit", " ".join(screen["text"]))
        p = self.p()
        self.assertIsNone(p["cards"])
        self.assertEqual(p["gold"], 980 + 20 * 20)

    def test_cards_new_day_refunds_pot(self):
        self.sit_at_cards()
        self.deal(6)
        self.game.act("u1", "cards.bet:10")
        self.next_day()
        self.game.rng = random.Random(1)
        self.game.view("u1")
        p = self.p()
        self.assertIsNone(p["cards"])
        self.assertEqual(p["gold"], 1000)
        self.assertEqual(p["loc"], "village")

    def test_cards_come_from_a_real_deck(self):
        self.sit_at_cards(gold=10 ** 9)
        self.edit(level=15)
        self.game.rng = random.Random(3)
        guesses = matches = 0
        for _ in range(4000):
            self.game.act("u1", "cards.bet:10")
            seen = [self.p()["cards"]["name"]]
            while self.p()["cards"]:
                card = self.p()["cards"]["card"]
                text = " ".join(self.game.act(
                    "u1", "cards.guess:" + ("high" if card <= 7 else "low"))["text"])
                guesses += 1
                matches += "A match!" in text
                game = self.p()["cards"]
                if game:
                    self.assertNotIn(game["name"], seen)  # no card dealt twice in a hand
                    seen.append(game["name"])
                    if len(seen) >= 4:
                        self.game.act("u1", "cards.cash")
        # A real deck matches 3/51 (5.9%) at most, versus 1/13 (7.7%) for endless rolls.
        self.assertLess(matches / guesses, 0.068)

    def test_cards_hand_from_before_decks_still_works(self):
        self.sit_at_cards()
        self.edit(cards={"bet": 20, "pot": 20, "card": 7, "name": "Seven of Moons",
                         "streak": 0}, gold=980)
        self.game.view("u1")
        self.assertIn("cards.guess:high", self.p()["allowed"])
        self.game.act("u1", "cards.guess:high")
        game = self.p()["cards"]
        if game:
            self.assertEqual(len(game["deck"]), 50)

    def test_cards_favour_the_house(self):
        self.sit_at_cards(gold=10 ** 9)
        self.edit(level=15)
        start = self.p()["gold"]
        rng = random.Random(7)
        for _ in range(3000):
            self.game.act("u1", "cards.bet:10")
            for _ in range(rng.randint(1, 4)):
                if not self.p()["cards"]:
                    break
                card = self.p()["cards"]["card"]
                self.game.act("u1", "cards.guess:" + ("high" if card <= 7 else "low"))
            if self.p()["cards"]:
                self.game.act("u1", "cards.cash")
        wagered = 3000 * 150
        self.assertLess(self.p()["gold"], start)
        self.assertGreater(self.p()["gold"], start - wagered * 0.4)

    # ------------------------------------------------------------- admin

    TEST_PASSWORD = "not-the-real-password"

    def admin_game(self):
        salt = b"0123456789abcdef"
        digest = hashlib.scrypt(self.TEST_PASSWORD.encode(), salt=salt, n=2 ** 10, r=8, p=1,
                                dklen=32)
        spec = "scrypt$1024$8$1$%s$%s" % (salt.hex(), digest.hex())
        self.game = Game(self.game.store, rng=random.Random(42), clock=lambda: self.now,
                         admin_hash=spec)

    def login(self, password=None):
        screen = self.game.view("u1")
        link = [l for l in screen["links"] if l["a"] == "admin.login"]
        self.assertTrue(link and link[0]["secret"])
        return self.game.act("u1", "admin.login", password or self.TEST_PASSWORD)

    def test_shipped_admin_hash_is_a_hash(self):
        self.assertTrue(ADMIN_HASH.startswith("scrypt$"))
        self.assertFalse(check_password("", ADMIN_HASH))
        self.assertFalse(check_password(self.TEST_PASSWORD, ADMIN_HASH))

    def test_date_on_town_square_is_the_hidden_entrance(self):
        self.admin_game()
        self.make()
        screen = self.game.view("u1")
        date_line = [t for t in screen["text"] if "[[" in t][0]
        self.assertIn("October 2026", date_line)
        self.assertNotIn("admin", " ".join(i["a"] for sec in screen["nav"] for i in sec["items"]))
        self.login()
        self.assertEqual(self.p()["loc"], "admin")

    def test_admin_wrong_password_and_lockout(self):
        self.admin_game()
        self.make()
        for _ in range(5):
            screen = self.login("guess")
            self.assertEqual(self.p()["loc"], "village")
        self.login()  # right password, but locked out
        self.assertEqual(self.p()["loc"], "village")
        self.now += timedelta(minutes=16)
        self.login()
        self.assertEqual(self.p()["loc"], "admin")

    def test_admin_actions_need_login(self):
        self.admin_game()
        self.make("u1", "Alice")
        self.make("u2", "Bob")
        screen = self.game.act("u1", "admin.set:u2:gold", "99999")
        self.assertIn("can't do that", screen["text"][0])
        self.assertEqual(self.p("u2")["gold"], 50)

    def test_admin_edits_other_players_and_self(self):
        self.admin_game()
        self.make("u1", "Alice")
        self.make("u2", "Bob")
        self.login()
        self.game.act("u1", "admin.pick:u2")
        self.game.act("u1", "admin.set:u2:gold", "12345")
        self.game.act("u1", "admin.set:u2:level", "99")  # clamped to 15
        self.game.act("u1", "admin.set:u2:gems", "lots")  # ignored
        bob = self.p("u2")
        self.assertEqual((bob["gold"], bob["level"], bob["gems"]), (12345, 15, 0))
        self.game.act("u1", "admin.alive:u2")
        self.assertFalse(self.p("u2")["alive"])
        self.game.act("u1", "admin.alive:u2")
        self.assertTrue(self.p("u2")["alive"])
        self.game.act("u1", "admin.pick:home")
        self.game.act("u1", "admin.pick:u1")
        self.game.act("u1", "admin.set:u1:gems", "7")
        self.assertEqual(self.p("u1")["gems"], 7)
        self.assertNotIn("admin.delete:u1", self.p("u1")["allowed"])

    def test_admin_delete_needs_name(self):
        self.admin_game()
        self.make("u1", "Alice")
        self.make("u2", "Bob")
        self.login()
        self.game.act("u1", "admin.pick:u2")
        self.game.act("u1", "admin.delete:u2", "bob?")
        self.assertIsNotNone(self.p("u2"))
        self.game.act("u1", "admin.delete:u2", "Bob")
        self.assertIsNone(self.p("u2"))
        self.assertEqual(self.p("u1")["loc"], "admin")

    def test_admin_settings_persist_and_reset(self):
        self.admin_game()
        self.make()
        self.login()
        self.game.act("u1", "admin.pick:settings")
        self.game.act("u1", "admin.opt:forest_turns", "50")
        self.game.act("u1", "admin.opt:bank_interest", "99")  # clamped to 20
        self.assertEqual((self.game.opt["forest_turns"], self.game.opt["bank_interest"]),
                         (50, 20.0))
        reloaded = Game(self.game.store, clock=lambda: self.now)
        self.assertEqual(reloaded.opt["forest_turns"], 50)
        self.game.act("u1", "admin.optreset")
        self.assertEqual(self.game.opt["forest_turns"], 20)
        self.assertEqual(Game(self.game.store).opt["forest_turns"], 20)

    def test_admin_session_expires(self):
        self.admin_game()
        self.make("u1", "Alice")
        self.make("u2", "Bob")
        self.login()
        self.now += timedelta(minutes=31)
        self.game.act("u1", "admin.pick:u2")
        self.game.act("u1", "admin.set:u2:gold", "1")
        self.assertEqual(self.p("u2")["gold"], 50)
        self.assertEqual(self.p("u1")["loc"], "village")

    def test_admin_news_and_chatter(self):
        self.admin_game()
        self.make()
        self.game.act("u1", "village.say", "hello [[0]] there")
        self.assertNotIn("[[", " ".join(self.game.view("u1")["text"]).replace(
            [t for t in self.game.view("u1")["text"] if "notice board" in t][0], ""))
        self.login()
        self.game.act("u1", "admin.news", "Feast tonight!")
        self.assertIn("Feast tonight!", self.game.store.recent_news(1)[0])
        self.game.act("u1", "admin.clearchat", "nope")
        self.assertTrue(self.game.store.chatter("village"))
        self.game.act("u1", "admin.clearchat", "clear")
        self.assertFalse(self.game.store.chatter("village"))

    def test_multiple_days_per_real_day(self):
        game = Game(Store(":memory:"), {"days_per_day": 4}, clock=lambda: self.now)
        self.assertEqual(game.today(), "2026-10-14 #3")


if __name__ == "__main__":
    unittest.main()
