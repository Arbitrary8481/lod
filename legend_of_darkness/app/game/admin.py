"""Hidden control panel for the game owner.

Opened by clicking the date on the town square and entering the admin password.
Only a salted scrypt hash of the password is stored here; it cannot be reversed.
"""

import hashlib
import hmac
import logging

from . import data as D

log = logging.getLogger("legend")

# scrypt$N$r$p$salt$hash
ADMIN_HASH = ("scrypt$16384$8$1$424e3fc08b70e9c67ce639dbb732b201$"
              "85a773150c257923aeaaf2228862f59612068a834e86f0376085e6a752763fbf")

ADMIN_SESSION = 30 * 60   # seconds an admin login lasts
ADMIN_MAX_FAILS = 5       # wrong passwords before lockout
ADMIN_LOCKOUT = 15 * 60   # seconds locked out

# (field, label, minimum, maximum)
EDITABLE = [
    ("level", "Level", 1, D.MAX_LEVEL),
    ("xp", "Experience", 0, 10 ** 9),
    ("hp", "Hit points", 1, 10 ** 6),
    ("gold", "Gold", 0, 10 ** 9),
    ("bank", "Bank", 0, 10 ** 9),
    ("gems", "Gems", 0, 10 ** 6),
    ("weapon", "Weapon tier", 0, len(D.WEAPONS) - 1),
    ("armor", "Armour tier", 0, len(D.ARMOR) - 1),
    ("turns", "Forest fights left", 0, 1000),
    ("pvp", "Warrior fights left", 0, 100),
    ("skill_uses", "Skill uses left", 0, 100),
    ("charm", "Charm", 0, 10 ** 6),
    ("dk", "Wyrm kills", 0, 1000),
    ("favor", "Favour", 0, 10 ** 6),
    ("bonus_hp", "Bonus max HP", 0, 10 ** 5),
    ("bonus_atk", "Bonus attack", 0, 10 ** 4),
    ("bonus_def", "Bonus defence", 0, 10 ** 4),
    ("bonus_turns", "Bonus daily fights", 0, 100),
]

# (key, label, type, minimum, maximum) - same ranges as the app's options schema
SETTINGS = [
    ("forest_turns", "Forest fights per day", int, 5, 100),
    ("pvp_fights", "Warrior fights per day", int, 0, 20),
    ("grave_fights", "Torments per day", int, 0, 50),
    ("bank_interest", "Bank interest %", float, 0, 20),
    ("days_per_day", "Game days per real day", int, 1, 4),
]


def check_password(password, spec):
    try:
        algo, n, r, p, salt, digest = spec.split("$")
        if algo != "scrypt":
            return False
        got = hashlib.scrypt(str(password).encode(), salt=bytes.fromhex(salt),
                             n=int(n), r=int(r), p=int(p), dklen=len(digest) // 2)
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(got.hex(), digest)


def _parse(value, kind, lo, hi):
    try:
        number = kind(str(value).strip())
    except (TypeError, ValueError):
        return None
    if number != number:  # NaN
        return None
    return max(lo, min(hi, number))


class AdminMixin:
    admin_hash = ADMIN_HASH

    def _now(self):
        return self.clock().timestamp()

    def _admin_ok(self, p):
        return p.get("admin_until", 0) > self._now()

    # ------------------------------------------------------------ login

    def do_admin_login(self, p, arg, value):
        now = self._now()
        if p.get("admin_lock_until", 0) > now:
            p["flash"].append("{w}The hands of the town clock refuse to move.{0}")
            return
        if check_password(value or "", self.admin_hash):
            p.update(admin_until=now + ADMIN_SESSION, admin_fails=0, admin_target=None,
                     loc="admin")
            log.info("Admin panel opened by %s", p["name"])
            return
        p["admin_fails"] = p.get("admin_fails", 0) + 1
        if p["admin_fails"] >= ADMIN_MAX_FAILS:
            p["admin_fails"] = 0
            p["admin_lock_until"] = now + ADMIN_LOCKOUT
            log.warning("Admin panel locked after failed attempts by %s", p["name"])
        p["flash"].append("{w}You squint at the date. Nothing happens.{0}")

    def do_admin_logout(self, p, arg, value):
        p["admin_until"] = 0
        p["loc"] = "village"

    # ------------------------------------------------------------- views

    def view_admin(self, p, s):
        if not self._admin_ok(p):
            p["loc"] = "village"
            p["admin_target"] = None
            s.say("{r}Your control panel session has expired.{0}", "")
            return self.view_village(p, s)
        target = p.get("admin_target")
        if target == "settings":
            return self._admin_settings_view(p, s)
        if target:
            t = self._admin_load(p, target)
            if t:
                return self._admin_player_view(p, s, t)
            p["admin_target"] = None
        self._admin_home_view(p, s)

    def _admin_home_view(self, p, s):
        players = sorted(self.store.all_players(), key=lambda t: t["name"].lower())
        s.say("{Y}Control Panel{0} - session ends in %d minutes."
              % max(1, (p["admin_until"] - self._now()) // 60), "")
        for t in players:
            s.say("{G}%s{0} - level %d, %d gold, %d in bank, %d wyrm kills%s"
                  % (t["name"], t["level"], t["gold"], t["bank"], t["dk"],
                     "" if t["alive"] else " {r}(dead){0}"))
        s.section("Characters")
        for t in players:
            s.add("Edit %s" % t["name"], "admin.pick:" + t["id"], "")
        s.section("Game")
        s.add("Game settings", "admin.pick:settings", "S")
        s.add("Post to the Daily News", "admin.news", "N",
              prompt="Announcement for the Daily News:")
        s.add("Clear village & inn chatter", "admin.clearchat", "C",
              prompt="Type CLEAR to erase all chatter:")
        s.section("Leave")
        s.add("Close control panel", "admin.logout", "X")

    def _admin_player_view(self, p, s, t):
        from .engine import attack, defence, max_hp
        s.say(
            "{Y}%s %s{0} (%s)" % (D.title_for(t["dk"]), t["name"],
                                  D.SPECIALTIES[t["specialty"]]["name"]),
            "Location: %s, %s. Last played: %s." % (
                t["loc"], "alive" if t["alive"] else "{r}dead{0}", t["last_day"] or "never"),
            "Max HP %d, attack %d, defence %d. Weapon: %s. Armour: %s." % (
                max_hp(t), attack(t), defence(t), D.WEAPONS[t["weapon"]], D.ARMOR[t["armor"]]),
        )
        s.section("Stats")
        for field, label, lo, hi in EDITABLE:
            s.add("%s: %s" % (label, t[field]), "admin.set:%s:%s" % (t["id"], field), "",
                  prompt="New %s for %s (%d-%d):" % (label.lower(), t["name"], lo, hi))
        s.section("Actions")
        s.add("Full heal", "admin.heal:" + t["id"], "")
        s.add("Revive" if not t["alive"] else "Kill", "admin.alive:" + t["id"], "")
        s.add("Give a fresh new day", "admin.newday:" + t["id"], "")
        if t["id"] != p["id"]:
            s.add("Delete character", "admin.delete:" + t["id"], "",
                  prompt="Type %s to permanently delete this character:" % t["name"])
        s.section("Back")
        s.add("Back to the control panel", "admin.pick:home", "B")

    def _admin_settings_view(self, p, s):
        overrides = self.store.get_settings()
        s.say("{Y}Game settings{0}",
              "Changes apply to everyone immediately and override the app's configuration "
              "page until reset.", "")
        s.section("Settings")
        for key, label, kind, lo, hi in SETTINGS:
            s.add("%s: %s%s" % (label, self.opt[key], " *" if key in overrides else ""),
                  "admin.opt:" + key, "", prompt="%s (%s-%s):" % (label, lo, hi))
        if overrides:
            s.say("{w}* changed here; the app configuration value is %s.{0}" % ", ".join(
                "%s=%s" % (k, self.base_opt[k]) for k in sorted(overrides)))
            s.add("Reset all to app configuration", "admin.optreset", "R")
        s.section("Back")
        s.add("Back to the control panel", "admin.pick:home", "B")

    # ----------------------------------------------------------- actions

    def _admin_load(self, p, pid):
        return p if pid == p["id"] else self.store.get_player(pid)

    def _admin_save(self, p, t):
        if t is not p:
            self.store.save_player(t)

    def _admin_guard(self, p):
        if self._admin_ok(p):
            return True
        p["loc"] = "village"
        return False

    def do_admin_pick(self, p, arg, value):
        if self._admin_guard(p):
            p["admin_target"] = None if arg == "home" else arg

    def do_admin_set(self, p, arg, value):
        if not self._admin_guard(p):
            return
        pid, _, field = arg.partition(":")
        spec = next((e for e in EDITABLE if e[0] == field), None)
        t = self._admin_load(p, pid)
        if not spec or not t:
            return
        number = _parse(value, int, spec[2], spec[3])
        if number is None:
            p["flash"].append("{r}That's not a number.{0}")
            return
        t[field] = number
        if field == "hp" and not t["alive"]:
            t["hp"] = 0
        self._admin_save(p, t)
        p["flash"].append("{G}%s's %s set to %d.{0}" % (t["name"], spec[1].lower(), number))
        log.info("Admin %s set %s.%s = %s", p["name"], t["name"], field, number)

    def do_admin_heal(self, p, arg, value):
        from .engine import max_hp
        t = self._admin_guard(p) and self._admin_load(p, arg)
        if t and t["alive"]:
            t["hp"] = max(t["hp"], max_hp(t))
            self._admin_save(p, t)
            p["flash"].append("{G}%s is fully healed.{0}" % t["name"])

    def do_admin_alive(self, p, arg, value):
        from .engine import max_hp
        t = self._admin_guard(p) and self._admin_load(p, arg)
        if not t:
            return
        if t["alive"]:
            t.update(alive=False, hp=0, fight=None, event=None, loc="shades")
            p["flash"].append("{r}%s has been struck down.{0}" % t["name"])
        else:
            t.update(alive=True, hp=max_hp(t))
            if t["loc"] == "shades":
                t["loc"] = "village"
            p["flash"].append("{G}%s has been revived.{0}" % t["name"])
        self._admin_save(p, t)

    def do_admin_newday(self, p, arg, value):
        t = self._admin_guard(p) and self._admin_load(p, arg)
        if t:
            t["last_day"] = None  # their next page load starts a new day
            self._admin_save(p, t)
            p["flash"].append("{G}%s will get a new day on their next move.{0}" % t["name"])

    def do_admin_delete(self, p, arg, value):
        t = self._admin_guard(p) and self._admin_load(p, arg)
        if not t or t is p:
            return
        if (value or "").strip() != t["name"]:
            p["flash"].append("{r}Name didn't match; nothing deleted.{0}")
            return
        self.store.delete_player(t["id"])
        p["admin_target"] = None
        p["flash"].append("{r}%s has been deleted.{0}" % t["name"])
        log.warning("Admin %s deleted character %s", p["name"], t["name"])

    def do_admin_opt(self, p, arg, value):
        if not self._admin_guard(p):
            return
        spec = next((e for e in SETTINGS if e[0] == arg), None)
        if not spec:
            return
        number = _parse(value, spec[2], spec[3], spec[4])
        if number is None:
            p["flash"].append("{r}That's not a number.{0}")
            return
        self.store.set_setting(arg, number)
        self.opt[arg] = number
        p["flash"].append("{G}%s set to %s.{0}" % (spec[1], number))
        log.info("Admin %s set option %s = %s", p["name"], arg, number)

    def do_admin_optreset(self, p, arg, value):
        if self._admin_guard(p):
            self.store.clear_settings()
            self.opt = dict(self.base_opt)
            p["flash"].append("{G}Settings reset to the app configuration.{0}")

    def do_admin_news(self, p, arg, value):
        from .engine import clean_text
        text = clean_text(value, 200)
        if self._admin_guard(p) and text:
            self.news("{Y}Town crier:{0} %s" % text)
            p["flash"].append("{G}Posted to the Daily News.{0}")

    def do_admin_clearchat(self, p, arg, value):
        if self._admin_guard(p) and (value or "").strip().upper() == "CLEAR":
            self.store.clear_chatter()
            p["flash"].append("{G}All chatter erased.{0}")
