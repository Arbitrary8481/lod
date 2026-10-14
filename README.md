# Legend of Darkness

A multiplayer fantasy text adventure for Home Assistant, in the spirit of the classic
BBS door games like *Legend of the Green Dragon* and *Legend of the Red Dragon*.

Each Home Assistant user gets their own character. Hunt in the Duskwood, train under
the village masters, ambush your housemates while they sleep in the fields, and finally
descend into the cavern to slay **the Shadow Wyrm**.

## Installing in Home Assistant

1. Go to **Settings → Apps → App store**, open the ⋮ menu and choose **Repositories**.
2. Add this repository's URL.
3. Install **Legend of Darkness**, start it, and enable **Show in sidebar**.

## Features

- **Daily turns**: forest fights, warrior fights and skill uses reset every game day.
- **Combat** against 60 creatures across 15 levels, with three specialties
  (Dark Arts, Mystical Powers, Thievery), each with its own combat skill.
- **Fourteen training masters** to defeat before you can face the Shadow Wyrm.
- **Wyrm kills** reset you to level 1 with a permanent gift and a new title.
- **Village**: weapon and armour shops with trade-ins, healer, bank with interest,
  and an inn with ale, gossip, a flirtatious bard and safe rooms.
- **Multiplayer**: ambush other players, a shared daily news feed, a hall of fame,
  and chat in the village square and the inn.
- **Death** sends you to the Shades, where you can torment souls to earn an early return.
- **Random forest events**: fairies, shrines, hermits, lost travellers and more.
- Keyboard hotkeys and a layout that works on phones.

## Development

```sh
pip install aiohttp
cd legend_of_darkness/app
DEV_MODE=1 DATA_DIR=../../.data python3 server.py
# open http://localhost:8099/?user=Alice  (use ?user=Bob in another tab for a second player)
```

Run the tests with `python3 -m unittest discover -s tests`.

### Layout

| Path | What it is |
| --- | --- |
| `legend_of_darkness/config.yaml` | Home Assistant app manifest (ingress, options) |
| `legend_of_darkness/app/server.py` | aiohttp server; identifies players by HA ingress headers |
| `legend_of_darkness/app/game/engine.py` | All game rules: locations, combat, new days |
| `legend_of_darkness/app/game/data.py` | Content: creatures, gear, masters, flavour text |
| `legend_of_darkness/app/game/store.py` | SQLite persistence in `/data/legend.db` |
| `legend_of_darkness/app/static/` | Browser UI |
