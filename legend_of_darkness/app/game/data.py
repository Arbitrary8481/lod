"""Static game content: equipment, creatures, masters, titles and flavour text."""

MAX_LEVEL = 15

VILLAGE = "Gloamhaven"
INN = "The Gloaming Lantern"
INNKEEPER = "Mordin"
BARD = "Seraphine"
DEALER = "One-Eyed Hesk"
CARD_RANKS = ["Ace", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten",
              "Jack", "Queen", "King"]
CARD_SUITS = ["Skulls", "Crowns", "Daggers", "Moons"]
HEALER = "Old Ysolde"
SMITH = "Garrick Ironhand"
ARMORER = "Bettany Steelweave"
BANKER = "Fenwick Coyne"
DEATH_LORD = "Malgrath, Keeper of Shades"
DRAGON = "the Shadow Wyrm"

WEAPONS = [
    "Bare Fists",
    "Splintered Club",
    "Rusted Dagger",
    "Hunting Knife",
    "Short Sword",
    "Hand Axe",
    "Flanged Mace",
    "Longsword",
    "War Hammer",
    "Battle Axe",
    "Bastard Sword",
    "Morning Star",
    "Halberd",
    "Runed Greatsword",
    "Moonsteel Blade",
    "Duskbane",
]

ARMOR = [
    "Threadbare Shirt",
    "Tattered Rags",
    "Padded Tunic",
    "Leather Vest",
    "Studded Leather",
    "Hide Armor",
    "Ring Mail",
    "Scale Mail",
    "Chain Mail",
    "Banded Mail",
    "Splint Mail",
    "Half Plate",
    "Full Plate",
    "Runed Plate",
    "Moonsteel Plate",
    "Duskwarden Aegis",
]


def gear_cost(tier):
    """Price of a weapon or armour tier at the shops."""
    if tier <= 0:
        return 0
    return int(round(90 * tier ** 1.9 / 5.0)) * 5


# (name, weapon) per creature level.
CREATURES = {
    1: [("Cave Rat", "gnashing teeth"), ("Mud Goblin", "a bent spoon"),
        ("Shadow Moth", "dusty wings"), ("Feral Hound", "snapping jaws")],
    2: [("Bog Lurker", "a slimy grip"), ("Grave Robber", "a rusty shovel"),
        ("Ghoul Pup", "cold little claws"), ("Thorn Sprite", "barbed vines")],
    3: [("Bandit Scout", "a notched shortsword"), ("Giant Spider", "venomous fangs"),
        ("Wisp of Gloom", "a chilling light"), ("Hill Wolf", "yellowed fangs")],
    4: [("Bone Archer", "a cracked longbow"), ("Swamp Hag", "a wicked hex"),
        ("Orc Raider", "a spiked club"), ("Bat Swarm", "a hundred leathery wings")],
    5: [("Ghoul", "rotting claws"), ("Hobgoblin Sergeant", "a jagged halberd"),
        ("Mire Serpent", "a crushing coil"), ("Cultist of the Void", "a sacrificial knife")],
    6: [("Werewolf", "savage claws"), ("Barrow Wight", "a grave-cold touch"),
        ("Highwayman", "a pair of flintlocks"), ("Carrion Crawler", "paralysing tendrils")],
    7: [("Wraith", "a life-draining grasp"), ("Forest Troll", "an uprooted sapling"),
        ("Gnoll Packleader", "a bone flail"), ("Dark Dryad", "strangling roots")],
    8: [("Ogre Brute", "a tree-trunk club"), ("Banshee", "a soul-rending wail"),
        ("Black Knight", "a cursed broadsword"), ("Harpy Matriarch", "razor talons")],
    9: [("Gargoyle", "stone fists"), ("Vampire Thrall", "hungry fangs"),
        ("Minotaur", "a great double axe"), ("Plague Bearer", "a festering touch")],
    10: [("Death Knight", "a runeblade of frost"), ("Shadow Stalker", "twin shadow daggers"),
         ("Hill Giant", "a boulder"), ("Basilisk", "a petrifying gaze")],
    11: [("Shadow Drake", "a breath of black fire"), ("Bone Golem", "grinding bone fists"),
         ("Witch of the Fens", "a storm of curses"), ("Wyvern", "a poisoned stinger")],
    12: [("Lich", "necrotic bolts"), ("Nightmare Steed", "burning hooves"),
         ("Chimera", "three hungry heads"), ("Vampire Lord", "a crimson rapier")],
    13: [("Abyssal Fiend", "hellforged claws"), ("Elder Wraith", "a howling void"),
         ("Frost Giant", "a glacier-hewn maul"), ("Beholder", "a dozen hateful eyes")],
    14: [("Void Horror", "unknowable tentacles"), ("Dread Lord", "a blade of pure night"),
         ("Pit Fiend", "a whip of chains"), ("Dracolich", "a breath of grave-dust")],
    15: [("Herald of the Wyrm", "a shadowflame glaive"), ("Eclipse Golem", "fists of dead stars"),
         ("Avatar of Despair", "a crushing sorrow"), ("Night Hag Queen", "a nightmare scythe")],
}

GHOSTS = [
    ("Wailing Shade", "a mournful shriek"),
    ("Restless Spirit", "spectral chains"),
    ("Forgotten Soul", "a hollow stare"),
    ("Drowned Revenant", "dripping fingers"),
    ("Hungry Phantom", "a gnawing chill"),
    ("Echo of a Tyrant", "a ghostly crown"),
]

# Master you face to advance FROM this level to the next.
MASTERS = {
    1: ("Old Brannoc", "a gnarled walking staff"),
    2: ("Sister Vey", "a pair of iron knuckles"),
    3: ("Tamsin the Quick", "dancing rapiers"),
    4: ("Hrolf Bearsbane", "a woodsman's axe"),
    5: ("Lady Morwen", "a silver-tipped spear"),
    6: ("Corvin Ashgrave", "a blackened scimitar"),
    7: ("Ysara of the Veil", "a staff of whispering wind"),
    8: ("Dunmore the Unbroken", "a tower shield and mace"),
    9: ("Kestrel Nightwing", "a hail of arrows"),
    10: ("Brother Aldous", "a flail of holy iron"),
    11: ("Sable Duskmantle", "a cloak of shadows"),
    12: ("Grimwald the Grey", "a runic greatsword"),
    13: ("Isolde Stormcaller", "crackling lightning"),
    14: ("Vharun, the Last Champion", "the sword that slew the last wyrm"),
}

TITLES = [
    "Peasant", "Squire", "Footman", "Knight", "Captain", "Champion",
    "Shadowbane", "Wyrmslayer", "Duskwarden", "Lightbringer", "Legend",
]


def title_for(dragon_kills):
    return TITLES[min(dragon_kills, len(TITLES) - 1)]


SPECIALTIES = {
    "dark": {
        "name": "Dark Arts",
        "skill": "Shadow Bolt",
        "blurb": "You were raised among the black candles and forbidden tomes. "
                 "Shadow answers when you call.",
        "help": "Hurl a bolt of shadow that ignores armour.",
    },
    "mystic": {
        "name": "Mystical Powers",
        "skill": "Mend",
        "blurb": "The old hedge-witches taught you the secret names of things. "
                 "Your wounds knit at your command.",
        "help": "Heal a large portion of your wounds mid-battle.",
    },
    "thief": {
        "name": "Thievery",
        "skill": "Backstab",
        "blurb": "You grew up in the alleys, quick of hand and quicker of knife.",
        "help": "A sure strike from the shadows for heavy damage.",
    },
}

DK_PERKS = {
    "hp": "+5 maximum hit points",
    "atk": "+1 attack",
    "def": "+1 defence",
    "turns": "+1 forest fight per day",
}

SPIRITS = [
    (-1, "{r}You wake feeling low in spirits.{0} (-1 forest fight)"),
    (0, "{w}You wake feeling ordinary.{0}"),
    (0, "{w}You wake feeling rested.{0}"),
    (1, "{G}You wake feeling high in spirits!{0} (+1 forest fight)"),
    (2, "{Y}You wake feeling VERY high in spirits!{0} (+2 forest fights)"),
]

VILLAGE_AMBIENCE = [
    "Lanterns gutter in the wind, though the sun has not truly risen in years.",
    "A crow watches you from the well, its eyes far too knowing.",
    "Somewhere a bell tolls, though no one admits to ringing it.",
    "The baker's apprentice hurries past, glancing nervously at the treeline.",
    "Fog curls through the cobbled lanes like something alive.",
    "A town crier mutters the day's dead from a crumpled scroll.",
]

FOREST_AMBIENCE = [
    "Black-barked trees crowd the path, their branches knitting out the sky.",
    "Something howls in the distance, and something else answers.",
    "The moss here glows faintly, the only light in the deep wood.",
    "Old bones lie half-buried in the leaf litter. Not all of them are animal.",
]

GOSSIP = [
    "They say the Shadow Wyrm only stirs for those who have mastered every teacher.",
    "Ysolde's tonics taste foul, but she's never lost a patient. Not one who paid, anyway.",
    "Fairies in the deep wood are fond of gems. Fonder than is healthy, some say.",
    "A warrior who takes no wounds in a fight feels bold enough to keep hunting.",
    "Heard the bank pays interest overnight. Gold in your pocket pays nothing but thieves.",
    "Rent a room upstairs if you don't fancy waking up with a knife in your ribs.",
]
