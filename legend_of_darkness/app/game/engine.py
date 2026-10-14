"""Game rules. Every request is: load player -> maybe new day -> run action -> render."""

import math
import random
import re
from datetime import datetime
from string import Template

from . import data as D
from .events import EVENTS

DEFAULT_OPTIONS = {
    "forest_turns": 20,
    "pvp_fights": 3,
    "grave_fights": 10,
    "bank_interest": 3.0,
    "days_per_day": 1,
}

NAME_RE = re.compile(r"^[A-Za-z][A-Za-z' -]{1,18}[A-Za-z]$")


def xp_for_kill(level):
    return int(round(10 * level ** 1.35))


def xp_needed(level):
    """Total experience required before you may challenge the master at `level`."""
    return sum((14 + 3 * i) * xp_for_kill(i) for i in range(1, level + 1))


def max_hp(p):
    return 10 * p["level"] + p["bonus_hp"]


def attack(p):
    return p["level"] + p["bonus_atk"] + p["weapon"]


def defence(p):
    return p["level"] + p["bonus_def"] + p["armor"]


def skill_max(p):
    return 1 + p["level"] // 3 + p["dk"] // 2


def heal_cost(p, amount):
    return int(math.ceil(amount * (0.5 + 0.35 * p["level"])))


def clean_text(text, limit):
    text = re.sub(r"[{}<>\x00-\x1f]", "", str(text or "")).strip()
    return text[:limit]


class Screen:
    def __init__(self, title):
        self.title = title
        self.text = []
        self.nav = []
        self._keys = set()

    def say(self, *lines):
        self.text.extend(lines)

    def section(self, heading):
        self.nav.append({"h": heading, "items": []})

    def add(self, label, action, key=None, prompt=None):
        if not self.nav:
            self.section("")
        key = key if key and key.upper() not in self._keys else self._auto_key(label)
        if key:
            self._keys.add(key.upper())
        item = {"k": key.upper() if key else "", "label": label, "a": action}
        if prompt:
            item["prompt"] = prompt
        self.nav[-1]["items"].append(item)

    def _auto_key(self, label):
        for ch in re.sub(r"\{.\}", "", label):
            if ch.isalpha() and ch.upper() not in self._keys:
                return ch.upper()
        for ch in "123456789":
            if ch not in self._keys:
                return ch
        return ""

    def actions(self):
        return [i["a"] for sec in self.nav for i in sec["items"]]


class Game:
    def __init__(self, store, options=None, rng=None, clock=None):
        self.store = store
        self.opt = dict(DEFAULT_OPTIONS)
        self.opt.update({k: v for k, v in (options or {}).items() if k in DEFAULT_OPTIONS})
        self.rng = rng or random.Random()
        self.clock = clock or datetime.now

    # ------------------------------------------------------------------ api

    def view(self, pid, display_name=""):
        p = self._load(pid, display_name)
        self._check_new_day(p)
        return self._finish(p)

    def act(self, pid, action, value=None, display_name=""):
        p = self._load(pid, display_name)
        if self._check_new_day(p):
            return self._finish(p)
        if action not in p["allowed"]:
            p["flash"].append("{r}You can't do that right now.{0}")
            return self._finish(p)
        verb, _, arg = action.partition(":")
        handler = getattr(self, "do_" + verb.replace(".", "_"), None)
        if handler:
            handler(p, arg, value)
        return self._finish(p)

    # ------------------------------------------------------------ plumbing

    def today(self):
        now = self.clock()
        dpd = max(1, min(4, int(self.opt["days_per_day"])))
        if dpd == 1:
            return now.strftime("%Y-%m-%d")
        return "%s #%d" % (now.strftime("%Y-%m-%d"), now.hour * dpd // 24 + 1)

    def _load(self, pid, display_name):
        p = self.store.get_player(pid)
        if p is None:
            p = {
                "id": pid, "name": None, "hint": clean_text(display_name, 20),
                "loc": "create", "level": 1, "xp": 0, "hp": 10, "gold": 50,
                "bank": 0, "gems": 0, "weapon": 1, "armor": 1,
                "bonus_hp": 0, "bonus_atk": 0, "bonus_def": 0, "bonus_turns": 0,
                "charm": 0, "dk": 0, "specialty": None, "alive": True,
                "turns": 0, "pvp": 0, "graves": 0, "soul": 0, "favor": 0,
                "skill_uses": 0, "ales": 0, "flirted": False, "master_lost": False,
                "room": False, "last_day": None, "fight": None, "event": None,
                "news_page": 0, "flash": [], "mail": [], "allowed": [],
            }
        return p

    def _finish(self, p):
        screen = self.render(p)
        p["allowed"] = screen.actions()
        self.store.save_player(p)
        return {
            "title": screen.title,
            "text": screen.text,
            "nav": screen.nav,
            "stats": self._stats(p),
        }

    def news(self, text):
        self.store.add_news(self.today(), text)

    def _check_new_day(self, p):
        if not p["specialty"] or p["last_day"] == self.today():
            return False
        self.start_day(p)
        return True

    def start_day(self, p):
        p["last_day"] = self.today()
        f = p["flash"]
        f.append("{Y}~ It is a new day in %s! ~{0}" % D.VILLAGE)
        bonus, line = self.rng.choice(D.SPIRITS)
        f.append(line)
        if not p["alive"]:
            p["alive"] = True
            f.append("{C}%s releases your soul. You awaken in the village, whole again.{0}"
                     % D.DEATH_LORD)
        p["hp"] = max(p["hp"], max_hp(p))
        if p["bank"] > 0 and self.opt["bank_interest"] > 0:
            interest = min(int(p["bank"] * self.opt["bank_interest"] / 100.0),
                           500 * p["level"])
            if interest:
                p["bank"] += interest
                f.append("{y}Your bank account earned {Y}%d{y} gold in interest.{0}" % interest)
        p["turns"] = max(1, int(self.opt["forest_turns"]) + p["bonus_turns"] + bonus)
        p["pvp"] = int(self.opt["pvp_fights"])
        p["graves"] = int(self.opt["grave_fights"])
        p["soul"] = max_hp(p)
        p["skill_uses"] = skill_max(p)
        p["ales"] = 0
        p["flirted"] = False
        p["master_lost"] = False
        p["room"] = False
        p["fight"] = None
        p["event"] = None
        if p["loc"] in ("fight", "event", "shades", "pvp"):
            p["loc"] = "village"
        f.append("You have {G}%d{0} forest fights today." % p["turns"])
        f.append("")

    def _die(self, p, cause):
        lost_xp = p["xp"] // 10
        p["alive"] = False
        p["hp"] = 0
        p["xp"] -= lost_xp
        lost_gold, p["gold"] = p["gold"], 0
        p["fight"] = None
        p["loc"] = "shades"
        p["flash"].extend([
            "{R}You have been slain!{0}",
            "You lose {y}%d{0} gold and {c}%d{0} experience." % (lost_gold, lost_xp),
            "Your soul drifts down into the Shades...",
            "",
        ])
        self.news("{R}%s{0} %s" % (p["name"], cause))
        return lost_gold

    # --------------------------------------------------------------- render

    def render(self, p):
        view = getattr(self, "view_" + p["loc"], self.view_village)
        title = {
            "create": "A Stranger Arrives", "create_spec": "Your Upbringing",
            "village": D.VILLAGE, "forest": "The Duskwood", "fight": "Battle!",
            "event": "Something Stirs", "weapons": "%s's Forge" % D.SMITH,
            "armor": "%s's Armoury" % D.ARMORER, "healer": "%s's Hut" % D.HEALER,
            "inn": D.INN, "bank": "Coyne & Daughters Bank", "training": "Training Grounds",
            "fame": "Hall of Fame", "news": "Daily News", "pvp": "The Fields",
            "shades": "The Shades", "dk": "Victory Over the Wyrm",
        }.get(p["loc"], D.VILLAGE)
        s = Screen(title)
        if p["mail"]:
            s.say("{C}--- While you were away ---{0}", *p["mail"])
            s.say("")
            p["mail"] = []
        if p["flash"]:
            s.say(*p["flash"])
            p["flash"] = []
        view(p, s)
        return s

    def _stats(self, p):
        if not p["specialty"]:
            return []
        spec = D.SPECIALTIES[p["specialty"]]
        hp_key = "hp" if p["alive"] else "soul"
        need = xp_needed(p["level"]) if p["level"] < D.MAX_LEVEL else None
        vital = [
            ["Level", str(p["level"]), None],
            ["Hit Points" if p["alive"] else "Soul",
             "%d / %d" % (p[hp_key], max_hp(p)), p[hp_key] / max(1, max_hp(p))],
            ["Experience", "%d / %s" % (p["xp"], need) if need else str(p["xp"]),
             min(1.0, p["xp"] / need) if need else None],
            ["Forest Fights", str(p["turns"]), None],
            ["Attack", str(attack(p)), None],
            ["Defence", str(defence(p)), None],
            ["%s" % spec["skill"], "%d / %d" % (p["skill_uses"], skill_max(p)), None],
        ]
        if not p["alive"]:
            vital.append(["Favour", str(p["favor"]), None])
            vital.append(["Torments Left", str(p["graves"]), None])
        return [
            {"h": "%s %s" % (D.title_for(p["dk"]), p["name"]), "rows": vital},
            {"h": "Possessions", "rows": [
                ["Gold", str(p["gold"]), None],
                ["Bank", str(p["bank"]), None],
                ["Gems", str(p["gems"]), None],
                ["Weapon", D.WEAPONS[p["weapon"]], None],
                ["Armour", D.ARMOR[p["armor"]], None],
            ]},
            {"h": "Renown", "rows": [
                ["Specialty", spec["name"], None],
                ["Charm", str(p["charm"]), None],
                ["Wyrm Kills", str(p["dk"]), None],
                ["Warrior Fights", str(p["pvp"]), None],
                ["Game Day", self.today(), None],
            ]},
        ]

    def _back_to_village(self, s, heading="Return"):
        s.section(heading)
        s.add("Return to %s" % D.VILLAGE, "goto:village", "V")

    # ---------------------------------------------------------- navigation

    def do_goto(self, p, arg, value):
        p["loc"] = arg
        if arg == "news":
            p["news_page"] = 0

    # ------------------------------------------------------------- creation

    def view_create(self, p, s):
        s.say(
            "{W}Darkness has lain over the land for a generation.{0}",
            "The sun is a pale coin behind the clouds, and the {m}Shadow Wyrm{0} "
            "stirs in the deep places beneath the Duskwood.",
            "",
            "You arrive at the gates of {G}%s{0}, the last lit village at the edge of "
            "the wood. The gatekeeper squints at you through the fog." % D.VILLAGE,
            "",
            "\"Well, stranger? What do they call you?\"",
            "",
            "{w}Names are 3-20 letters; spaces, hyphens and apostrophes allowed.{0}",
        )
        s.section("Your Name")
        if p["hint"] and NAME_RE.match(p["hint"]):
            s.add("I am %s" % p["hint"], "create.name:hint", "I")
        s.add("Give a name", "create.name", "N", prompt="What do they call you?")

    def do_create_name(self, p, arg, value):
        name = p["hint"] if arg == "hint" else str(value or "")
        name = re.sub(r"\s+", " ", name).strip()
        if not NAME_RE.match(name):
            p["flash"].append("{r}\"That's no name I can pronounce,\" the gatekeeper grumbles.{0}")
            return
        if self.store.name_taken(name, p["id"]):
            p["flash"].append("{r}\"There's already a %s in these parts. Try another.\"{0}" % name)
            return
        p["name"] = name
        p["loc"] = "create_spec"

    def view_create_spec(self, p, s):
        s.say("\"%s, is it? And how were you raised, %s?\"" % (p["name"], p["name"]), "")
        s.section("Your Upbringing")
        for key, spec in D.SPECIALTIES.items():
            s.say("{G}%s{0} - %s {w}(%s: %s){0}" % (spec["name"], spec["blurb"],
                                                   spec["skill"], spec["help"]))
            s.add(spec["name"], "create.spec:" + key)

    def do_create_spec(self, p, arg, value):
        if arg not in D.SPECIALTIES:
            return
        p["specialty"] = arg
        p["loc"] = "village"
        p["flash"].append("The gatekeeper nods and swings the gate open. \"Welcome to %s. "
                          "Try not to die.\"" % D.VILLAGE)
        p["flash"].append("")
        self.news("{G}%s{0} has arrived in %s, seeking glory." % (p["name"], D.VILLAGE))
        self.start_day(p)

    # -------------------------------------------------------------- village

    def view_village(self, p, s):
        if not p["alive"]:
            return self.view_shades(p, s)
        s.say(
            "{G}%s{0}, the last lit village before the Duskwood. Smoke curls from the "
            "chimney of %s, and the clang of %s's hammer rings across the square."
            % (D.VILLAGE, D.INN, D.SMITH.split()[0]),
            "{w}%s{0}" % self.rng.choice(D.VILLAGE_AMBIENCE),
            "",
            "{c}Nearby, villagers talk:{0}",
        )
        talk = self.store.chatter("village", 8)
        if talk:
            for author, text in talk:
                s.say("  {G}%s{0} says, \"{W}%s{0}\"" % (author, text))
        else:
            s.say("  {w}The square is quiet.{0}")
        s.section("City Gates")
        s.add("The Duskwood", "goto:forest", "F")
        s.add("Slay Other Warriors", "goto:pvp", "S")
        s.add("Training Grounds", "goto:training", "T")
        s.section("Market Street")
        s.add("%s's Forge" % D.SMITH.split()[0], "goto:weapons", "W")
        s.add("%s's Armoury" % D.ARMORER.split()[0], "goto:armor", "A")
        s.add("The Bank", "goto:bank", "B")
        s.add("%s's Hut" % D.HEALER, "goto:healer", "H")
        s.section("Tavern Lane")
        s.add(D.INN, "goto:inn", "I")
        s.section("Other")
        s.add("Daily News", "goto:news", "N")
        s.add("Hall of Fame", "goto:fame", "O")
        s.add("Speak", "village.say", "K", prompt="Say something to the village:")
        s.add("Look Around", "goto:village", "L")

    def do_village_say(self, p, arg, value):
        text = clean_text(value, 200)
        if text:
            self.store.add_chatter("village", p["name"], text)

    # --------------------------------------------------------------- forest

    def view_forest(self, p, s):
        s.say(
            "{g}The Duskwood.{0} %s" % self.rng.choice(D.FOREST_AMBIENCE),
            "",
            "You have {G}%d{0} forest fights remaining today." % p["turns"],
        )
        s.section("Hunt")
        if p["turns"] > 0:
            s.add("Look for Trouble", "forest.search:normal", "L")
            s.add("Go Thrillseeking", "forest.search:thrill", "T")
            if p["level"] > 1:
                s.add("Go Slumming", "forest.search:slum", "S")
            if p["level"] >= D.MAX_LEVEL:
                s.add("{R}Seek the Shadow Wyrm{0}", "forest.dragon", "D")
        else:
            s.say("{r}You are too weary to hunt any more today.{0}")
        s.section("Paths")
        s.add("%s's Hut" % D.HEALER, "goto:healer", "H")
        s.add("Return to %s" % D.VILLAGE, "goto:village", "V")

    def do_forest_search(self, p, arg, value):
        if p["turns"] <= 0:
            return
        p["turns"] -= 1
        if self.rng.random() < 0.15:
            p["turns"] += 1  # strange happenings don't cost a fight
            return self.forest_event(p)
        level = p["level"] + {"thrill": 1, "slum": -1}.get(arg, 0)
        level = max(1, level)
        foe = self.make_creature(level)
        if arg == "thrill":
            foe["gold"] = int(foe["gold"] * 1.25)
            foe["xp"] = int(foe["xp"] * 1.25)
        p["flash"].append("{g}You stalk through the trees and encounter {R}%s{g}, "
                          "who comes at you with {R}%s{g}!{0}" % (foe["name"], foe["weapon"]))
        self.start_fight(p, "forest", foe, back="forest")

    def do_forest_dragon(self, p, arg, value):
        if p["turns"] <= 0 or p["level"] < D.MAX_LEVEL:
            return
        p["turns"] -= 1
        dk = p["dk"]
        foe = {
            "name": D.DRAGON.capitalize(), "weapon": "jaws of living night", "level": 18,
            "hp": 300 + 20 * dk, "atk": 37 + 2 * dk, "def": 22 + dk, "gold": 0, "xp": 0,
        }
        p["flash"].extend([
            "{m}You descend into the cavern at the heart of the Duskwood. The air is cold "
            "and thick with the stink of ash.{0}",
            "{R}Two burning eyes open in the dark. %s has awoken.{0}" % D.DRAGON.capitalize(),
        ])
        self.start_fight(p, "dragon", foe, back="forest")

    def make_creature(self, level):
        names = D.CREATURES[min(level, D.MAX_LEVEL)]
        name, weapon = self.rng.choice(names)
        return {
            "name": name, "weapon": weapon, "level": level,
            "hp": max(4, int(round((2 + 5 * level) * self.rng.uniform(0.85, 1.15)))),
            "atk": round((2.1 * level - 0.8) * self.rng.uniform(0.9, 1.15), 1),
            "def": float(level),
            "gold": int(round(22 * level * self.rng.uniform(0.7, 1.3))),
            "xp": xp_for_kill(level),
        }

    # --------------------------------------------------------------- events

    def forest_event(self, p):
        pool = [(k, e) for k, e in EVENTS.items() if p["level"] >= e.get("min_level", 1)]
        key, ev = self._weighted(pool, lambda kv: kv[1]["weight"])
        p["loc"] = "forest"
        if "outcomes" in ev:
            self._resolve(p, ev["outcomes"])
        else:
            p["event"] = key
            p["loc"] = "event"

    def _weighted(self, items, weight):
        roll = self.rng.uniform(0, sum(weight(i) for i in items))
        for item in items:
            roll -= weight(item)
            if roll <= 0:
                return item
        return items[-1]

    def _fill(self, text, p):
        return Template(text).safe_substitute(
            name=p["name"], village=D.VILLAGE, healer=D.HEALER, innkeeper=D.INNKEEPER)

    def view_event(self, p, s):
        ev = EVENTS.get(p["event"] or "")
        if not ev or "choices" not in ev:
            p["event"] = None
            p["loc"] = "forest"
            return self.view_forest(p, s)
        s.say(*[self._fill(line, p) for line in ev["intro"]])
        s.section("What Do You Do?")
        for i, choice in enumerate(ev["choices"]):
            s.add(self._fill(choice["label"], p), "event.choose:%d" % i)

    def do_event_choose(self, p, arg, value):
        ev = EVENTS.get(p["event"] or "")
        try:
            choice = ev["choices"][int(arg)]
        except (TypeError, KeyError, ValueError, IndexError):
            return
        cost = choice.get("cost", {})
        price = {"gold": cost.get("gold", 0) * p["level"], "gems": cost.get("gems", 0),
                 "turns": cost.get("turns", 0)}
        if any(p[k] < v for k, v in price.items()):
            # Can't pay: say so and let them pick something else.
            p["flash"].append(self._fill(choice.get("broke", "{r}You can't afford that.{0}"), p))
            return
        for k, v in price.items():
            p[k] -= v
        p["event"] = None
        p["loc"] = "forest"
        if choice.get("news"):
            self.news(self._fill(choice["news"], p))
        self._resolve(p, choice["outcomes"], price)

    def _resolve(self, p, outcomes, paid=None):
        _, effects, text = self._weighted(outcomes, lambda o: o[0])
        parts = ["-%d %s" % (v, k if k != "turns" else "forest fights")
                 for k, v in (paid or {}).items() if v]
        p["flash"].append(self._fill(text, p))
        fight = self._apply_effects(p, effects, parts)
        if parts:
            p["flash"].append("{w}(%s){0}" % ", ".join(parts))
        p["flash"].append("")
        if fight:
            self._event_fight(p, fight)

    def _apply_effects(self, p, effects, parts):
        lvl = p["level"]
        mhp = max_hp(p)

        def note(n, one, many):
            if n:
                parts.append("%+d %s" % (n, one if abs(n) == 1 else many))

        for key, val in effects.items():
            if key == "gold":
                if val > 0:
                    n = int(round(val * lvl * self.rng.uniform(0.8, 1.2)))
                else:
                    n = -min(p["gold"], -val * lvl)
                p["gold"] += n
                note(n, "gold", "gold")
            elif key == "gold_pct":
                n = int(p["gold"] * val)
                p["gold"] += n
                note(n, "gold", "gold")
            elif key == "gems":
                n = max(val, -p["gems"])
                p["gems"] += n
                note(n, "gem", "gems")
            elif key == "hp_pct":
                if val > 0:
                    n = max(0, min(mhp - p["hp"], int(math.ceil(mhp * val))))
                else:
                    n = -max(0, min(p["hp"] - 1, int(math.ceil(mhp * -val))))
                p["hp"] += n
                note(n, "HP", "HP")
            elif key == "turns":
                n = max(val, -p["turns"])
                p["turns"] += n
                note(n, "forest fight", "forest fights")
            elif key == "charm":
                n = max(val, -p["charm"])
                p["charm"] += n
                note(n, "charm", "charm")
            elif key == "xp":
                n = val * xp_for_kill(lvl)
                p["xp"] += n
                note(n, "experience", "experience")
            elif key == "max_hp":
                p["bonus_hp"] += val
                p["hp"] += val
                note(val, "max HP", "max HP")
            elif key == "atk":
                p["bonus_atk"] += val
                note(val, "attack", "attack")
            elif key == "def":
                p["bonus_def"] += val
                note(val, "defence", "defence")
            elif key == "skill":
                n = max(0, min(val, skill_max(p) - p["skill_uses"]))
                p["skill_uses"] += n
                skill = D.SPECIALTIES[p["specialty"]]["skill"]
                note(n, "%s use" % skill, "%s uses" % skill)
            elif key == "news":
                self.news(self._fill(val, p))
        return effects.get("fight")

    def _event_fight(self, p, spec):
        if spec.get("mirror"):
            foe = {
                "name": spec["name"], "weapon": spec["weapon"], "level": p["level"],
                "hp": max(5, max_hp(p) * 4 // 5), "atk": float(attack(p)),
                "def": float(defence(p)), "gold": 22 * p["level"],
                "xp": xp_for_kill(p["level"]),
            }
        else:
            foe = self.make_creature(max(1, p["level"] + spec.get("level", 0)))
            foe.update(name=spec["name"], weapon=spec["weapon"])
        reward = spec.get("reward", 1.0)
        foe["gold"] = int(foe["gold"] * reward)
        foe["xp"] = int(foe["xp"] * reward)
        self.start_fight(p, "forest", foe, back="forest")

    # --------------------------------------------------------------- combat

    def start_fight(self, p, kind, foe, back, target=None):
        foe = dict(foe, kind=kind, back=back, maxhp=foe["hp"], target=target, hurt=False)
        p["fight"] = foe
        p["loc"] = "fight"

    def strike(self, atk, dfn):
        roll = atk * self.rng.uniform(0.5, 1.5) - dfn * self.rng.uniform(0.25, 0.75)
        return max(0, int(round(roll)))

    def view_fight(self, p, s):
        f = p["fight"]
        if not f:
            p["loc"] = "village"
            return self.view_village(p, s)
        hp_key = "soul" if f["kind"] == "grave" else "hp"
        s.say(
            "",
            "{R}%s{0}  HP: {R}%d{0}/%d   |   {G}You{0}  %s: {G}%d{0}/%d"
            % (f["name"], f["hp"], f["maxhp"], "Soul" if hp_key == "soul" else "HP",
               p[hp_key], max_hp(p)),
        )
        s.section("Fight")
        s.add("Attack", "fight.attack", "A")
        if p["skill_uses"] > 0 and f["kind"] != "grave":
            s.add(D.SPECIALTIES[p["specialty"]]["skill"], "fight.skill", "K")
        s.add("Yield" if f["kind"] == "master" else "Flee", "fight.flee", "F")

    def do_fight_attack(self, p, arg, value):
        self.combat_round(p, "attack")

    def do_fight_skill(self, p, arg, value):
        if p["skill_uses"] > 0:
            self.combat_round(p, "skill")

    def do_fight_flee(self, p, arg, value):
        self.combat_round(p, "flee")

    def combat_round(self, p, mode):
        f = p["fight"]
        if not f:
            return
        out = p["flash"]
        kind = f["kind"]
        hp_key = "soul" if kind == "grave" else "hp"

        if mode == "flee":
            if kind == "master":
                out.append("{w}You lower your weapon and yield. %s nods. \"Come back when "
                           "you're ready.\"{0}" % f["name"])
                p["fight"] = None
                p["loc"] = "training"
                return
            chance = {"dragon": 0.25, "pvp": 0.4}.get(kind, 0.5)
            if self.rng.random() < chance:
                out.append("{y}You flee like a coward, but you live.{0}")
                out.append("")
                p["fight"] = None
                p["loc"] = f["back"]
                return
            out.append("{r}You try to flee, but {R}%s{r} blocks your escape!{0}" % f["name"])
        elif mode == "skill":
            p["skill_uses"] -= 1
            spec = p["specialty"]
            if spec == "dark":
                dmg = self.rng.randint(2 * p["level"] + 8, 3 * p["level"] + 10)
                f["hp"] -= dmg
                out.append("{M}You hurl a bolt of living shadow at %s for {W}%d{M} damage!{0}"
                           % (f["name"], dmg))
            elif spec == "mystic":
                heal = min(max_hp(p) - p["hp"], max(2, max_hp(p) * 35 // 100))
                p["hp"] += max(0, heal)
                out.append("{M}You speak a secret name and your wounds knit. "
                           "You heal {W}%d{M} hit points.{0}" % max(0, heal))
            else:
                dmg = max(1, int(round(attack(p) * self.rng.uniform(1.5, 2.2)
                                       - f["def"] * 0.4)))
                f["hp"] -= dmg
                out.append("{M}You slip into the shadows and strike %s from behind for "
                           "{W}%d{M} damage!{0}" % (f["name"], dmg))
        else:
            dmg = self.strike(attack(p), f["def"])
            if dmg:
                f["hp"] -= dmg
                out.append("{G}You hit {R}%s{G} for {W}%d{G} damage!{0}" % (f["name"], dmg))
            else:
                out.append("{g}You try to hit {R}%s{g} but {r}MISS{g}!{0}" % f["name"])

        if f["hp"] <= 0:
            return self.win_fight(p, f)

        dmg = self.strike(f["atk"], defence(p))
        if dmg:
            p[hp_key] -= dmg
            f["hurt"] = True
            out.append("{R}%s{r} hits you with %s for {W}%d{r} damage!{0}"
                       % (f["name"], f["weapon"], dmg))
        else:
            out.append("{R}%s{g} tries to hit you but misses!{0}" % f["name"])

        if p[hp_key] <= 0:
            p[hp_key] = 0
            return self.lose_fight(p, f)

    def win_fight(self, p, f):
        out = p["flash"]
        kind = f["kind"]
        p["fight"] = None
        p["loc"] = f["back"]
        out.append("")
        if kind == "forest":
            p["gold"] += f["gold"]
            p["xp"] += f["xp"]
            out.append("{Y}You have slain %s!{0}" % f["name"])
            out.append("You find {Y}%d{0} gold and gain {C}%d{0} experience." % (f["gold"], f["xp"]))
            if self.rng.random() < 0.04:
                p["gems"] += 1
                out.append("{C}A gem rolls out of the corpse!{0}")
            if not f["hurt"]:
                p["turns"] += 1
                out.append("{G}A perfect fight! You feel invigorated.{0} (+1 forest fight)")
        elif kind == "master":
            p["level"] += 1
            p["hp"] = max_hp(p)
            p["skill_uses"] = max(p["skill_uses"], skill_max(p))
            out.extend([
                "{Y}You have defeated %s!{0}" % f["name"],
                "\"Well fought,\" says %s. \"I have nothing more to teach you.\"" % f["name"],
                "{G}You are now level %d!{0} Your maximum hit points, attack and defence "
                "increase." % p["level"],
            ])
            self.news("{G}%s{0} has defeated the master {W}%s{0} and reached level %d!"
                      % (p["name"], f["name"], p["level"]))
        elif kind == "dragon":
            p["loc"] = "dk"
            self.news("{Y}%s{0} has slain {R}%s{0}! Light returns to %s, if only for a "
                      "while." % (p["name"], D.DRAGON, D.VILLAGE))
        elif kind == "pvp":
            self._pvp_win(p, f)
        elif kind == "grave":
            favor = 10 + p["level"]
            p["favor"] += favor
            out.append("{C}The soul of %s is torn apart. %s is pleased.{0} (+%d favour)"
                       % (f["name"], D.DEATH_LORD.split(",")[0], favor))
        out.append("")

    def lose_fight(self, p, f):
        out = p["flash"]
        kind = f["kind"]
        out.append("")
        if kind == "forest":
            self._die(p, "was slain in the Duskwood by {R}%s{0}." % f["name"])
        elif kind == "dragon":
            self._die(p, "was devoured by {R}%s{0}." % D.DRAGON)
        elif kind == "master":
            p["fight"] = None
            p["hp"] = 1
            p["master_lost"] = True
            p["loc"] = "training"
            out.extend([
                "{r}%s stands over you, weapon lowered.{0}" % f["name"],
                "\"Not yet. Rest, train, and come back tomorrow.\"",
                "",
            ])
        elif kind == "pvp":
            target = self.store.get_player(f["target"])
            gold = self._die(p, "was slain trying to ambush {W}%s{0}." % f["name"])
            if target:
                target["gold"] += gold
                target["mail"].append("{G}%s ambushed you in the fields and lost! You took "
                                      "%d gold from the body.{0}" % (p["name"], gold))
                self.store.save_player(target)
        elif kind == "grave":
            p["fight"] = None
            p["graves"] = 0
            p["loc"] = "shades"
            out.extend(["{r}Your soul is too battered to torment anyone else today.{0}", ""])

    # ------------------------------------------------------------ wyrm kill

    def view_dk(self, p, s):
        s.say(
            "{Y}%s lets out a final, shuddering roar and collapses.{0}" % D.DRAGON.capitalize(),
            "For a heartbeat true sunlight spills into the cavern.",
            "",
            "{w}But the darkness is patient. Its heart still beats beneath the earth, and "
            "the blow has cost you everything: your strength, your gear, your gold. "
            "You will wake in %s as a stranger once more... but not unchanged.{0}"
            % D.VILLAGE,
            "",
            "Choose the gift the dying light grants you:",
        )
        s.section("Choose a Gift")
        for key, label in D.DK_PERKS.items():
            s.add(label, "dk.perk:" + key)

    def do_dk_perk(self, p, arg, value):
        if arg not in D.DK_PERKS:
            return
        p["dk"] += 1
        p["bonus_hp"] += 5 if arg == "hp" else 0
        p["bonus_atk"] += 1 if arg == "atk" else 0
        p["bonus_def"] += 1 if arg == "def" else 0
        p["bonus_turns"] += 1 if arg == "turns" else 0
        p.update(level=1, xp=0, gold=50, bank=0, weapon=1, armor=1, loc="village")
        p["hp"] = max_hp(p)
        p["skill_uses"] = skill_max(p)
        p["flash"].extend([
            "{Y}You are reborn as %s %s.{0} (%s)" % (D.title_for(p["dk"]), p["name"],
                                                    D.DK_PERKS[arg]),
            "",
        ])

    # ----------------------------------------------------------------- shops

    def _shop_view(self, p, s, kind):
        names = D.WEAPONS if kind == "weapons" else D.ARMOR
        current = p["weapon" if kind == "weapons" else "armor"]
        trade = int(D.gear_cost(current) * 0.75)
        if kind == "weapons":
            s.say("{W}%s{0} wipes soot from his brow. \"Need something sharper than %s?\""
                  % (D.SMITH, D.WEAPONS[current].lower()))
        else:
            s.say("{W}%s{0} looks you up and down. \"%s won't stop much. Let's fix that.\""
                  % (D.ARMORER, D.ARMOR[current]))
        s.say("Your current gear is worth {y}%d{0} gold in trade." % trade, "")
        s.section("For Sale")
        for tier in range(1, len(names)):
            if tier == current:
                continue
            cost = D.gear_cost(tier)
            colour = "{G}" if p["gold"] + trade >= cost else "{w}"
            label = "%s%s{0} (%s %d) - %d gold" % (
                colour, names[tier], "dmg" if kind == "weapons" else "def", tier, cost)
            s.add(label, "%s.buy:%d" % (kind, tier), "")
        self._back_to_village(s)

    def _shop_buy(self, p, kind, tier):
        slot = "weapon" if kind == "weapons" else "armor"
        names = D.WEAPONS if kind == "weapons" else D.ARMOR
        try:
            tier = int(tier)
        except ValueError:
            return
        if not 1 <= tier < len(names) or tier == p[slot]:
            return
        trade = int(D.gear_cost(p[slot]) * 0.75)
        net = D.gear_cost(tier) - trade
        if p["gold"] < net:
            p["flash"].append("{r}You can't afford the %s.{0}" % names[tier])
            return
        p["gold"] -= net
        old, p[slot] = p[slot], tier
        p["flash"].append("{G}You trade in your %s and walk away with a %s!{0}"
                          % (names[old], names[tier]))
        if net < 0:
            p["flash"].append("You receive {y}%d{0} gold in change." % -net)

    def view_weapons(self, p, s):
        self._shop_view(p, s, "weapons")

    def view_armor(self, p, s):
        self._shop_view(p, s, "armor")

    def do_weapons_buy(self, p, arg, value):
        self._shop_buy(p, "weapons", arg)

    def do_armor_buy(self, p, arg, value):
        self._shop_buy(p, "armor", arg)

    # ---------------------------------------------------------------- healer

    def view_healer(self, p, s):
        missing = max_hp(p) - p["hp"]
        s.say("{W}%s{0} stirs a bubbling pot of something green and foul." % D.HEALER)
        s.section("Healing")
        if missing <= 0:
            s.say("\"You're healthy as an ox. Begone.\"")
        else:
            s.say("\"Wounded, are we? %d gold for the lot. Or %d to patch the worst of it.\""
                  % (heal_cost(p, missing), heal_cost(p, (missing + 1) // 2)))
            s.add("Complete healing (%d gold)" % heal_cost(p, missing), "healer.heal:full", "C")
            s.add("Patch up half (%d gold)" % heal_cost(p, (missing + 1) // 2),
                  "healer.heal:half", "P")
        s.section("Leave")
        s.add("Back to the Duskwood", "goto:forest", "F")
        s.add("Return to %s" % D.VILLAGE, "goto:village", "V")

    def do_healer_heal(self, p, arg, value):
        missing = max_hp(p) - p["hp"]
        amount = missing if arg == "full" else (missing + 1) // 2
        if amount <= 0:
            return
        cost = heal_cost(p, amount)
        if p["gold"] < cost:
            p["flash"].append("{r}\"No gold, no tonic,\" Ysolde snaps.{0}")
            return
        p["gold"] -= cost
        p["hp"] += amount
        p["flash"].append("{G}You gag down the tonic. %d hit points restored.{0}" % amount)

    # ------------------------------------------------------------------- inn

    def view_inn(self, p, s):
        s.say(
            "{y}%s{0} is warm, smoky and loud. %s polishes a tankard behind the bar, and "
            "%s the bard tunes her lute by the fire." % (D.INN, D.INNKEEPER, D.BARD),
            "",
        )
        talk = self.store.chatter("inn", 6)
        if talk:
            s.say("{c}Snatches of conversation:{0}")
            for author, text in talk:
                s.say("  {G}%s{0} says, \"{W}%s{0}\"" % (author, text))
            s.say("")
        s.section("The Bar")
        s.add("Buy an ale (%d gold)" % (5 * p["level"]), "inn.ale", "A")
        s.add("Listen to gossip", "inn.gossip", "G")
        s.add("Flirt with %s" % D.BARD, "inn.flirt", "F")
        s.add("Speak", "inn.say", "K", prompt="Say something to the room:")
        s.section("Upstairs")
        if p["room"]:
            s.say("{G}Your room upstairs is paid for tonight. You're safe from ambush.{0}")
        else:
            s.add("Rent a room (%d gold)" % (15 * p["level"]), "inn.room", "R")
        self._back_to_village(s)

    def do_inn_ale(self, p, arg, value):
        cost = 5 * p["level"]
        if p["ales"] >= 3:
            p["flash"].append("{r}%s takes your tankard away. \"You've had enough.\"{0}"
                              % D.INNKEEPER)
        elif p["gold"] < cost:
            p["flash"].append("{r}\"Coin first,\" grunts %s.{0}" % D.INNKEEPER)
        else:
            p["gold"] -= cost
            p["ales"] += 1
            heal = max(0, min(max_hp(p) - p["hp"], max(1, max_hp(p) // 10)))
            p["hp"] += heal
            p["flash"].append("{y}You down a frothy ale. Liquid courage!{0} (+%d HP)" % heal)

    def do_inn_gossip(self, p, arg, value):
        p["flash"].append("{w}%s leans in: \"%s\"{0}" % (D.INNKEEPER, self.rng.choice(D.GOSSIP)))
        recent = self.store.recent_news(4)
        if recent:
            p["flash"].append("{c}Around the tables you hear:{0}")
            p["flash"].extend("  " + n for n in recent)
        p["flash"].append("")

    def do_inn_flirt(self, p, arg, value):
        if p["flirted"]:
            p["flash"].append("%s is busy with her lute. Maybe tomorrow." % D.BARD)
            return
        p["flirted"] = True
        if self.rng.random() < min(0.9, 0.5 + p["charm"] * 0.02):
            p["charm"] += 1
            p["flash"].append("{M}%s laughs and sings a verse about your bravery. "
                              "You feel more charming!{0} (+1 charm)" % D.BARD)
        else:
            p["flash"].append("{r}%s raises an eyebrow and plays a song about a fool. "
                              "The whole tavern laughs.{0}" % D.BARD)

    def do_inn_say(self, p, arg, value):
        text = clean_text(value, 200)
        if text:
            self.store.add_chatter("inn", p["name"], text)

    def do_inn_room(self, p, arg, value):
        cost = 15 * p["level"]
        if p["room"]:
            return
        if p["gold"] < cost:
            p["flash"].append("{r}You can't afford a room.{0}")
            return
        p["gold"] -= cost
        p["room"] = True
        p["flash"].append("{G}You pay for a room. Nobody will find you there tonight.{0}")

    # ------------------------------------------------------------------ bank

    def view_bank(self, p, s):
        s.say("{W}%s{0} peers over his spectacles. \"Your balance stands at {Y}%d{0} gold. "
              "Interest is paid each morning on deposits.\"" % (D.BANKER, p["bank"]))
        s.section("Banking")
        s.add("Deposit all", "bank.deposit:all", "D")
        s.add("Deposit some", "bank.deposit", "E", prompt="How much gold to deposit?")
        s.add("Withdraw all", "bank.withdraw:all", "W")
        s.add("Withdraw some", "bank.withdraw", "I", prompt="How much gold to withdraw?")
        self._back_to_village(s)

    def _amount(self, arg, value, maximum):
        if arg == "all":
            return maximum
        try:
            return max(0, min(maximum, int(str(value).strip())))
        except (TypeError, ValueError):
            return 0

    def do_bank_deposit(self, p, arg, value):
        amount = self._amount(arg, value, p["gold"])
        p["gold"] -= amount
        p["bank"] += amount
        p["flash"].append("You deposit {Y}%d{0} gold." % amount)

    def do_bank_withdraw(self, p, arg, value):
        amount = self._amount(arg, value, p["bank"])
        p["bank"] -= amount
        p["gold"] += amount
        p["flash"].append("You withdraw {Y}%d{0} gold." % amount)

    # -------------------------------------------------------------- training

    def view_training(self, p, s):
        s.say("{w}Warriors spar in the muddy yard, watched by the masters of %s.{0}" % D.VILLAGE)
        s.section("Training")
        if p["level"] >= D.MAX_LEVEL:
            s.say("", "You have bested every master. {R}Only %s remains.{0}" % D.DRAGON)
        else:
            master, weapon = D.MASTERS[p["level"]]
            need = xp_needed(p["level"])
            s.say("", "Your master is {W}%s{0}, who fights with %s." % (master, weapon))
            if p["xp"] >= need:
                s.say("{G}%s says you are ready to face them.{0}" % master)
            else:
                s.say("%s says you need {C}%d{0} more experience." % (master, need - p["xp"]))
            if p["master_lost"]:
                s.say("{r}You have already lost to your master today.{0}")
            s.add("Challenge %s" % master, "training.challenge", "C")
        self._back_to_village(s)

    def do_training_challenge(self, p, arg, value):
        if p["level"] >= D.MAX_LEVEL:
            return
        master, weapon = D.MASTERS[p["level"]]
        if p["master_lost"]:
            p["flash"].append("{r}%s waves you off. \"Tomorrow.\"{0}" % master)
            return
        if p["xp"] < xp_needed(p["level"]):
            p["flash"].append("{r}%s laughs. \"You're not ready.\"{0}" % master)
            return
        lvl = p["level"]
        foe = {
            "name": master, "weapon": weapon, "level": lvl + 1,
            "hp": int(round((2 + 5 * lvl) * 1.5)),
            "atk": round((2.1 * lvl - 0.8) * 1.1, 1), "def": float(lvl),
            "gold": 0, "xp": 0,
        }
        p["flash"].append("{W}%s takes up %s. \"Show me what you've learned.\"{0}"
                          % (master, weapon))
        self.start_fight(p, "master", foe, back="training")

    # ------------------------------------------------------------------ pvp

    def _pvp_targets(self, p):
        today = self.today()
        out = []
        for t in self.store.all_players():
            if t["id"] == p["id"] or not t.get("specialty") or not t["alive"]:
                continue
            if t["level"] < p["level"] - 1:
                continue
            if t["room"] and t["last_day"] == today:
                continue
            out.append(t)
        return sorted(out, key=lambda t: (-t["level"], t["name"]))

    def view_pvp(self, p, s):
        s.say("{w}Out in the fields beyond the walls, warriors who couldn't afford a room "
              "sleep under the stars. Easy prey... or a nasty surprise.{0}",
              "You can attack warriors no more than one level below you.",
              "You have {G}%d{0} warrior fights left today." % p["pvp"], "")
        s.section("Sleeping Warriors")
        targets = self._pvp_targets(p) if p["pvp"] > 0 else []
        for t in targets:
            s.add("%s %s (level %d)" % (D.title_for(t["dk"]), t["name"], t["level"]),
                  "pvp.attack:" + t["id"], "")
        if not targets:
            s.say("{w}There is no one here you can attack.{0}")
        self._back_to_village(s)

    def do_pvp_attack(self, p, arg, value):
        if p["pvp"] <= 0:
            return
        target = next((t for t in self._pvp_targets(p) if t["id"] == arg), None)
        if not target:
            p["flash"].append("{r}They're no longer there.{0}")
            return
        p["pvp"] -= 1
        foe = {
            "name": target["name"], "weapon": "their " + D.WEAPONS[target["weapon"]].lower(),
            "level": target["level"], "hp": max_hp(target),
            "atk": attack(target), "def": defence(target), "gold": 0, "xp": 0,
        }
        p["flash"].append("{R}You creep up on %s as they sleep... they wake just in time!{0}"
                          % target["name"])
        self.start_fight(p, "pvp", foe, back="village", target=target["id"])

    def _pvp_win(self, p, f):
        out = p["flash"]
        target = self.store.get_player(f["target"])
        if not target:
            return
        gold = target["gold"]
        xp = min(target["xp"] // 10, 40 * target["level"])
        p["gold"] += gold
        p["xp"] += xp
        target["gold"] = 0
        target["xp"] -= xp // 2
        target["alive"] = False
        target["hp"] = 0
        target["loc"] = "shades"
        target["fight"] = None
        target["mail"].append("{R}%s ambushed you as you slept in the fields! You lost %d gold "
                              "and your life.{0}" % (p["name"], gold))
        self.store.save_player(target)
        out.append("{Y}You have slain %s!{0} You take {Y}%d{0} gold and gain {C}%d{0} experience."
                   % (target["name"], gold, xp))
        self.news("{R}%s{0} ambushed and slew {W}%s{0} in the fields."
                  % (p["name"], target["name"]))

    # ---------------------------------------------------------------- shades

    def view_shades(self, p, s):
        p["loc"] = "shades"
        s.say(
            "{m}You stand among the restless dead in the Shades. Grey figures drift past, "
            "moaning.{0} On a throne of bone sits {W}%s{0}." % D.DEATH_LORD,
            "",
            "You will return to life with the new day, or sooner if you can earn "
            "{C}100 favour{0} by tormenting other souls.",
            "Current favour: {C}%d{0}. Torments left: {C}%d{0}." % (p["favor"], p["graves"]),
        )
        s.section("The Shades")
        if p["graves"] > 0 and p["soul"] > 0:
            s.add("Torment a soul", "shades.torment", "T")
        if p["favor"] >= 100:
            s.add("Beg for resurrection (100 favour)", "shades.resurrect", "R")
        s.section("Other")
        s.add("Daily News", "goto:news", "N")
        s.add("Hall of Fame", "goto:fame", "O")
        s.add("Look around", "goto:shades", "L")

    def do_shades_torment(self, p, arg, value):
        if p["alive"] or p["graves"] <= 0 or p["soul"] <= 0:
            return
        p["graves"] -= 1
        name, weapon = self.rng.choice(D.GHOSTS)
        foe = self.make_creature(p["level"])
        foe.update(name=name, weapon=weapon, gold=0, xp=0)
        p["flash"].append("{m}You drift toward %s.{0}" % name)
        self.start_fight(p, "grave", foe, back="shades")

    def do_shades_resurrect(self, p, arg, value):
        if p["alive"] or p["favor"] < 100:
            return
        p["favor"] -= 100
        p["alive"] = True
        p["hp"] = max(1, max_hp(p) // 2)
        p["loc"] = "village"
        p["flash"].append("{C}%s waves a skeletal hand. You gasp awake in the village "
                          "square.{0}" % D.DEATH_LORD.split(",")[0])
        self.news("{C}%s{0} was granted a return from the Shades." % p["name"])

    # ------------------------------------------------------------ fame/news

    def view_fame(self, p, s):
        players = sorted(self.store.all_players(),
                         key=lambda t: (-t["dk"], -t["level"], -t["xp"]))
        s.say("{Y}Carved into the old oak wall are the names of %s's greatest:{0}" % D.VILLAGE, "")
        for i, t in enumerate(players[:20], 1):
            s.say("{W}%2d.{0} {G}%s %s{0} - level %d, %d wyrm kill%s%s"
                  % (i, D.title_for(t["dk"]), t["name"], t["level"], t["dk"],
                     "" if t["dk"] == 1 else "s", "" if t["alive"] else " {r}(dead){0}"))
        s.section("Return")
        s.add("Return", "goto:" + ("village" if p["alive"] else "shades"), "V")

    def view_news(self, p, s):
        days = self.store.news_days()
        page = min(p["news_page"], max(0, len(days) - 1))
        if not days:
            s.say("{w}Nothing of note has happened. Yet.{0}")
        else:
            day = days[page]
            s.say("{Y}News for %s{0}" % day, "")
            for line in self.store.news_for(day):
                s.say("- " + line)
        s.section("News")
        if page + 1 < len(days):
            s.add("Previous day", "news.page:older", "P")
        if page > 0:
            s.add("Next day", "news.page:newer", "X")
        s.add("Return", "goto:" + ("village" if p["alive"] else "shades"), "V")

    def do_news_page(self, p, arg, value):
        p["news_page"] = max(0, p["news_page"] + (1 if arg == "older" else -1))
