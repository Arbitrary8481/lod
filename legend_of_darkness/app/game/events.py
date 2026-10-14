"""Random forest encounters.

Each event has a `weight` (how often it appears), optional `min_level`, `intro` lines
and either:
  - `outcomes`: resolved immediately, or
  - `choices`: the player picks one, then one of its `outcomes` is rolled.

An outcome is (weight, effects, text). Effects:
  gold      n -> n * level gold (negative loses carried gold)
  gold_pct  fraction of carried gold (negative loses it)
  gems      gems gained or lost
  hp_pct    fraction of max HP healed (+) or lost (-); never kills
  turns     forest fights gained or lost
  charm     charm gained or lost
  xp        n -> n * a normal kill's experience at your level
  max_hp / atk / def   permanent bonuses
  skill     specialty skill uses restored (capped at the daily max)
  fight     {"name", "weapon", "level": +offset, "reward": multiplier, "mirror": bool}
  news      line for the Daily News ($name is replaced)

A choice may have a `cost` ({"gold": n * level, "gems": n, "turns": n}) and a
`broke` line shown when the player can't pay; they then pick again.

Text may use $name, $village, $healer and $innkeeper.
"""

EVENTS = {
    # ------------------------------------------------------------ instant
    "pouch": {
        "weight": 4,
        "outcomes": [(1, {"gold": 25}, "{Y}You trip over a rotting pouch. Coins spill out!{0}")],
    },
    "gem": {
        "weight": 3,
        "outcomes": [(1, {"gems": 1}, "{C}Something sparkles in a stream bed. You fish out a gem!{0}")],
    },
    "pit": {
        "weight": 3,
        "outcomes": [(1, {"hp_pct": -0.2}, "{r}The ground gives way! You tumble into a hunter's "
                                           "pit and scrape your way out.{0}")],
    },
    "camp": {
        "weight": 3,
        "outcomes": [(1, {"gold": 6, "hp_pct": 0.15},
                      "{g}You find an abandoned camp. A few coins and a half-finished skin of "
                      "wine restore you a little.{0}")],
    },
    "hermit": {
        "weight": 3,
        "outcomes": [
            (1, {"charm": 1}, "{G}An old hermit pinches your cheek. \"Such a pretty one!\"{0}"),
            (1, {"charm": -1}, "{r}An old hermit whacks you with an ugly stick.{0}"),
        ],
    },
    "minstrel": {
        "weight": 2,
        "outcomes": [
            (1, {"turns": 1}, "{M}A wandering minstrel plays a rousing march. Your feet itch "
                              "for adventure.{0}"),
            (1, {"charm": 1}, "{M}A wandering minstrel teaches you a bawdy verse. The ladies and "
                              "lads of $village will love it.{0}"),
        ],
    },
    "raven": {
        "weight": 2,
        "outcomes": [(1, {"gold_pct": -0.1}, "{r}A raven swoops down, snatches a beakful of coins "
                                              "from your purse and cackles off into the gloom.{0}")],
    },
    "spring": {
        "weight": 2,
        "outcomes": [(1, {"hp_pct": 0.5}, "{C}You find a spring of clear, cold water. Drinking "
                                          "from it washes your pain away.{0}")],
    },
    "corpse": {
        "weight": 2,
        "outcomes": [
            (3, {"gold": 15}, "{w}You find the body of a less fortunate adventurer. Their purse "
                              "is still full.{0}"),
            (1, {"gold": 10, "gems": 1}, "{w}You find the body of a less fortunate adventurer, "
                                         "clutching a gem in a death grip.{0}"),
            (1, {"hp_pct": -0.15}, "{r}You search the body of a fallen adventurer. It searches "
                                   "you back, with teeth, before you put it down for good.{0}"),
        ],
    },

    # ------------------------------------------------------------ choices
    "fairy": {
        "weight": 3,
        "intro": ["{M}A tiny fairy darts out of the gloom and hovers before your nose.{0}",
                  "\"Gem? Gem? Shiny gem for a gift?\" she pleads."],
        "choices": [
            {"label": "Give her a gem", "cost": {"gems": 1},
             "broke": "{r}You have no gems! The fairy kicks you in the nose and vanishes.{0}",
             "outcomes": [
                 (1, {"turns": 2}, "{M}Fairy dust fills your lungs. You feel energised!{0}"),
                 (1, {"max_hp": 1}, "{M}The fairy kisses your brow. You feel permanently "
                                    "hardier!{0}"),
                 (1, {"hp_pct": 1.0}, "{M}The fairy sings and your wounds close completely.{0}"),
             ]},
            {"label": "Shoo her away",
             "outcomes": [(1, {}, "The fairy sticks out her tongue and zips away.")]},
        ],
    },
    "shrine": {
        "weight": 2,
        "intro": ["{m}You come upon a shrine of black stone, slick with old offerings. "
                  "A whisper invites you to kneel.{0}"],
        "choices": [
            {"label": "Kneel and pray", "outcomes": [
                (1, {"hp_pct": 1.0, "turns": 1}, "{G}Warmth floods through you. You feel "
                                                 "eager to fight!{0}"),
                (1, {"hp_pct": -0.25}, "{R}Something cold drinks from you.{0}"),
            ]},
            {"label": "Walk away", "outcomes": [(1, {}, "You leave the shrine to its whispering.")]},
        ],
    },
    "traveler": {
        "weight": 2,
        "intro": ["{w}A lost merchant sits weeping beside a broken cart. \"Please, the road "
                  "back to $village - which way?\"{0}",
                  "Guiding them will cost you a forest fight."],
        "choices": [
            {"label": "Guide them home", "cost": {"turns": 1},
             "broke": "{r}You're too exhausted to guide anyone.{0}",
             "outcomes": [
                 (7, {"gold": 25}, "{Y}The grateful merchant rewards you handsomely.{0}"),
                 (3, {"gems": 1}, "{C}At the village gate the merchant presses a gem into "
                                  "your hand.{0}"),
             ]},
            {"label": "Point vaguely and leave", "outcomes": [
                (1, {}, "You point in a direction. Any direction. The merchant thanks you."),
            ]},
        ],
    },
    "chest": {
        "weight": 3,
        "intro": ["{y}Half-buried under the roots of a dead oak sits an iron-banded chest.{0}",
                  "The lock is rusted. The lid is ever so slightly ajar."],
        "choices": [
            {"label": "Open it", "outcomes": [
                (45, {"gold": 35}, "{Y}The chest is full of old coins!{0}"),
                (15, {"gold": 20, "gems": 1}, "{Y}Coins, and nestled among them, a gem!{0}"),
                (20, {"fight": {"name": "Mimic", "weapon": "a lid full of teeth", "level": 1,
                                "reward": 2.0}},
                 "{R}The chest yawns open, revealing rows of teeth. It's a MIMIC!{0}"),
                (20, {"hp_pct": -0.25}, "{r}A poisoned needle springs from the lock. Ouch.{0}"),
            ]},
            {"label": "Leave it be", "outcomes": [
                (1, {}, "Some things are best left buried. You walk on."),
            ]},
        ],
    },
    "mushrooms": {
        "weight": 3,
        "intro": ["{g}A ring of pale, softly glowing mushrooms grows in a clearing. They smell "
                  "like honey and rain.{0}"],
        "choices": [
            {"label": "Eat one", "outcomes": [
                (30, {"hp_pct": 1.0}, "{G}Delicious! Warmth spreads through your limbs.{0}"),
                (25, {"turns": 2}, "{G}Your heart races. You could run for days!{0}"),
                (15, {"max_hp": 1}, "{M}The world shimmers. When it settles, you feel sturdier "
                                    "than before.{0}"),
                (30, {"hp_pct": -0.3, "turns": -1}, "{r}Your stomach knots. You spend some time "
                                                    "behind a tree regretting your choices.{0}"),
            ]},
            {"label": "Leave them alone", "outcomes": [
                (1, {}, "You've heard what happens to people who eat strange mushrooms."),
            ]},
        ],
    },
    "witch": {
        "weight": 2,
        "intro": ["{m}At a crossroads, a crone sits on a stump, shuffling cards made of "
                  "bone.{0}",
                  "\"Your fortune, dearie? Ten coins a level. Cheap at twice the price.\""],
        "choices": [
            {"label": "Pay for a fortune", "cost": {"gold": 10},
             "broke": "{r}\"No coin, no fortune.\" She cackles.{0}",
             "outcomes": [
                 (35, {"xp": 3}, "{C}\"The Tower, reversed. Learn from your failures.\" You "
                                 "suddenly understand where you've been going wrong.{0}"),
                 (25, {"charm": 2}, "{M}\"The Lovers! Someone in $village fancies you.\" You "
                                    "walk taller.{0}"),
                 (20, {"skill": 2}, "{M}\"The Magician.\" Power tingles in your fingertips.{0}"),
                 (20, {"turns": -1}, "{r}\"Death.\" She won't say more. You spend some time "
                                     "nervously looking over your shoulder.{0}"),
             ]},
            {"label": "Mock her", "outcomes": [
                (1, {"charm": -1}, "{r}She curses you with warts. You feel less charming.{0}"),
                (1, {"turns": -2}, "{r}She turns you into a toad! It takes a while to hop "
                                   "back to normal.{0}"),
                (1, {}, "She just laughs. That's somehow worse."),
            ]},
            {"label": "Walk on", "outcomes": [(1, {}, "\"Another time, dearie.\"")]},
        ],
    },
    "knight": {
        "weight": 2,
        "intro": ["{w}A knight in dented armour lies propped against a tree, bleeding "
                  "badly.{0}",
                  "\"Water... please...\""],
        "choices": [
            {"label": "Tend their wounds", "outcomes": [
                (6, {"hp_pct": -0.2, "xp": 2, "charm": 1},
                 "{G}You bind their wounds with strips of your own cloak. They teach you a trick "
                 "or two before limping home.{0}"),
                (4, {"hp_pct": -0.2, "gems": 1, "charm": 1},
                 "{G}You patch them up. In thanks, they give you a gem from their sword hilt.{0}"),
            ]},
            {"label": "Rob them", "outcomes": [
                (6, {"gold": 30, "charm": -2}, "{r}You cut their purse and walk away. You feel "
                                               "a little dirtier.{0}"),
                (4, {"charm": -1, "fight": {"name": "Wounded Knight", "weapon": "a notched "
                                            "longsword", "level": 1, "reward": 1.5}},
                 "{R}They weren't as weak as they looked!{0}"),
            ]},
            {"label": "Leave them", "outcomes": [
                (1, {}, "Their pleas follow you down the path for a long time."),
            ]},
        ],
    },
    "dice": {
        "weight": 2,
        "intro": ["{y}A pair of goblins squat around a lantern, rolling knucklebones.{0}",
                  "\"Oi! Fancy a game? Twenty a level, winner takes the pot!\""],
        "choices": [
            {"label": "Roll the bones", "cost": {"gold": 20},
             "broke": "{r}The goblins jeer at your empty purse.{0}",
             "outcomes": [
                 (40, {"gold": 40}, "{Y}Snake eyes for them, sixes for you! You scoop up the "
                                    "pot.{0}"),
                 (10, {"gold": 60, "gems": 1}, "{Y}You win so hard one of the goblins throws in "
                                               "a gem to save face!{0}"),
                 (50, {}, "{r}The bones betray you. The goblins cackle as they pocket your "
                          "coins.{0}"),
             ]},
            {"label": "Flip their lantern over", "outcomes": [
                (1, {"fight": {"name": "Goblin Cardsharp", "weapon": "loaded dice and a shiv",
                               "level": 0, "reward": 1.5}},
                 "{R}One goblin flees. The other draws a shiv!{0}"),
            ]},
            {"label": "Decline", "outcomes": [(1, {}, "\"Yer loss!\"")]},
        ],
    },
    "bandits": {
        "weight": 2, "min_level": 2,
        "intro": ["{R}A rope snaps taut across the path. Bandits melt out of the trees.{0}",
                  "\"Toll road, friend. A quarter of your purse and you walk away.\""],
        "choices": [
            {"label": "Pay the toll", "outcomes": [
                (1, {"gold_pct": -0.25}, "{y}You hand over the coins. The bandits laugh and "
                                         "wave you through.{0}"),
            ]},
            {"label": "Fight the captain", "outcomes": [
                (1, {"fight": {"name": "Bandit Captain", "weapon": "a wicked cutlass",
                               "level": 1, "reward": 1.5}},
                 "{R}\"Brave. Stupid, but brave.\" The captain steps forward.{0}"),
            ]},
            {"label": "Run for it", "outcomes": [
                (6, {}, "{G}You crash through the undergrowth and lose them.{0}"),
                (4, {"hp_pct": -0.15}, "{r}An arrow catches you as you flee.{0}"),
            ]},
        ],
    },
    "well": {
        "weight": 2,
        "intro": ["{c}An old stone well stands alone in a clearing, far from any house. "
                  "Something glints far below.{0}"],
        "choices": [
            {"label": "Toss in a coin and wish", "cost": {"gold": 1},
             "broke": "{r}You don't have a single coin to wish with.{0}",
             "outcomes": [
                 (3, {"gems": 1}, "{C}A gem floats up on a sudden bubble!{0}"),
                 (3, {"hp_pct": 1.0}, "{C}A cool mist rises and soothes your wounds.{0}"),
                 (4, {}, "Plink. Nothing happens. Wishes are like that."),
             ]},
            {"label": "Climb down", "outcomes": [
                (4, {"gold": 50}, "{Y}At the bottom, a drowned fortune in coins!{0}"),
                (3, {"hp_pct": -0.3}, "{r}The rope snaps. You fall a very long way.{0}"),
                (3, {"fight": {"name": "Well Lurker", "weapon": "slimy, grasping arms",
                               "level": 1, "reward": 2.0}},
                 "{R}Something in the water was waiting for you.{0}"),
            ]},
            {"label": "Leave it", "outcomes": [(1, {}, "You don't trust wells.")]},
        ],
    },
    "tome": {
        "weight": 2,
        "intro": ["{m}A book bound in pale leather lies open on a tree stump, its pages "
                  "turning in a wind you can't feel.{0}"],
        "choices": [
            {"label": "Read it", "outcomes": [
                (4, {"xp": 3}, "{C}Ancient battle-lore fills your mind.{0}"),
                (3, {"skill": 3}, "{M}The words burn into your memory. Your specialty "
                                  "feels sharper.{0}"),
                (3, {"turns": -1, "charm": -1}, "{r}The words crawl. You come to some time "
                                                "later, muttering.{0}"),
            ]},
            {"label": "Burn it", "outcomes": [
                (1, {"charm": 1}, "{G}It screams as it burns. You feel you've done the world "
                                  "a service.{0}"),
            ]},
            {"label": "Leave it", "outcomes": [(1, {}, "You back away slowly.")]},
        ],
    },
    "hatchling": {
        "weight": 1, "min_level": 5,
        "intro": ["{R}In a hollow lined with bones, a wyrm hatchling sleeps curled atop a "
                  "small hoard.{0}",
                  "Its smoky breath rises and falls."],
        "choices": [
            {"label": "Sneak in and grab some treasure", "outcomes": [
                (6, {"gold": 60, "gems": 1}, "{Y}You tiptoe out with your pockets full!{0}"),
                (4, {"fight": {"name": "Wyrm Hatchling", "weapon": "a gout of black flame",
                               "level": 2, "reward": 2.0}},
                 "{R}A coin clinks. One golden eye opens.{0}"),
            ]},
            {"label": "Back away quietly", "outcomes": [
                (1, {}, "Let sleeping wyrms lie."),
            ]},
        ],
    },
    "child": {
        "weight": 2,
        "intro": ["{w}A small child sits crying beneath a tree. \"I followed a light and now "
                  "I can't find home...\"{0}",
                  "Taking them back to $village will cost you a forest fight."],
        "choices": [
            {"label": "Take them home", "cost": {"turns": 1},
             "broke": "{r}You're too exhausted. You point them toward the village lights.{0}",
             "outcomes": [
                 (1, {"charm": 2, "gold": 10}, "{G}Their parents weep with joy and press coins "
                                               "into your hands.{0}"),
             ],
             "news": "{G}$name{0} rescued a lost child from the Duskwood."},
            {"label": "Ignore them", "outcomes": [
                (1, {"charm": -1}, "{r}You walk on. You feel a little colder inside.{0}"),
            ]},
        ],
    },
    "lady": {
        "weight": 1, "min_level": 8,
        "intro": ["{C}Mist parts to reveal a silver pool under a moon that shouldn't be "
                  "visible.{0}",
                  "A pale hand rises from the water, palm up. Waiting for an offering."],
        "choices": [
            {"label": "Offer two gems", "cost": {"gems": 2},
             "broke": "{r}You don't have enough gems. The hand sinks back beneath the water.{0}",
             "outcomes": [
                 (1, {"atk": 1}, "{Y}The water blesses your weapon arm. You feel permanently "
                                 "stronger!{0}"),
                 (1, {"def": 1}, "{Y}The water hardens your skin. You feel permanently "
                                 "tougher!{0}"),
             ],
             "news": "{C}$name{0} received a blessing from the Lady of the Silver Pool."},
            {"label": "Leave", "outcomes": [
                (1, {}, "The mist closes behind you. You'll never find this place again. "
                        "Probably."),
            ]},
        ],
    },
    "doppelganger": {
        "weight": 1, "min_level": 3,
        "intro": ["{m}A figure steps out of the shadows. It has your face, your gear, your "
                  "stance. It smiles your smile.{0}"],
        "choices": [
            {"label": "Fight your reflection", "outcomes": [
                (1, {"fight": {"name": "Your Shadow", "weapon": "your own moves", "level": 0,
                               "reward": 3.0, "mirror": True}},
                 "{R}It draws its weapon the moment you draw yours.{0}"),
            ]},
            {"label": "Flee", "outcomes": [
                (1, {}, "You run. When you glance back, it's still standing there, waving."),
            ]},
        ],
    },
    "caravan": {
        "weight": 2,
        "intro": ["{y}A merchant caravan has stopped to water its horses. The trader waves "
                  "you over to see her wares.{0}"],
        "choices": [
            {"label": "Buy a healing draught (15 gold a level)", "cost": {"gold": 15},
             "broke": "{r}\"Come back when you have coin.\"{0}",
             "outcomes": [(1, {"hp_pct": 1.0}, "{G}It tastes of cherries. You feel wonderful.{0}")]},
            {"label": "Buy a gem (60 gold a level)", "cost": {"gold": 60},
             "broke": "{r}\"Gems aren't cheap, love.\"{0}",
             "outcomes": [(1, {"gems": 1}, "{C}She hands you a gem wrapped in silk.{0}")]},
            {"label": "Move on", "outcomes": [(1, {}, "\"Safe travels!\"")]},
        ],
    },
    "statue": {
        "weight": 2,
        "intro": ["{w}A moss-covered statue of a forgotten hero stands in a clearing. Its "
                  "stone sword is pitted with age.{0}"],
        "choices": [
            {"label": "Pray to the hero", "outcomes": [
                (1, {"skill": 1}, "{M}A faint warmth answers your prayer.{0}"),
                (1, {}, "Nothing happens. The hero is long dead."),
            ]},
            {"label": "Pry loose the gem in its eye", "outcomes": [
                (5, {"gems": 1, "charm": -1}, "{C}It pops free. You could swear the statue "
                                              "looks disappointed.{0}"),
                (5, {"fight": {"name": "Animated Statue", "weapon": "a stone sword",
                               "level": 1, "reward": 1.5}},
                 "{R}Stone grinds against stone. The statue turns its head toward you.{0}"),
            ]},
            {"label": "Move on", "outcomes": [(1, {}, "You nod respectfully and move on.")]},
        ],
    },
}
