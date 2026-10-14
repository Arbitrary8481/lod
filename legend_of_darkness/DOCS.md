# Legend of Darkness

Open **Legend of Darkness** from the sidebar. Each Home Assistant user plays their own
character, so everyone in the household can compete for the hall of fame.

## How to play

- Choose a name and an upbringing (specialty). Your specialty gives you a combat skill.
- Each game day you get a number of **forest fights**. Hunt in the Duskwood for gold and
  experience. Visit the healer when you're hurt.
- Once you have enough experience, defeat your master at the **Training Grounds** to level up.
- At level 15, seek out **the Shadow Wyrm** in the forest.
- If you die, you lose the gold you were carrying and some experience. You come back the
  next game day, or sooner if you earn enough favour in the Shades.
- Gold in the bank is safe and earns interest. Gold in your pocket can be stolen by other
  players who ambush you in the fields. Rent a room at the inn to stay safe overnight.

Press the highlighted letter next to any action to choose it from the keyboard.

## Options

| Option | Default | Description |
| --- | --- | --- |
| `forest_turns` | 20 | Forest fights per game day |
| `pvp_fights` | 3 | Ambushes per game day |
| `grave_fights` | 10 | Torments per game day while dead |
| `bank_interest` | 3 | Percent interest on bank deposits each new day |
| `days_per_day` | 1 | Game days per real day (1-4) |

Game days follow Home Assistant's time zone. Saves are kept in the app's `/data` folder
and are included in Home Assistant backups.
