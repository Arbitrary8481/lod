"""HTTP front end. Home Assistant ingress supplies the user identity via headers."""

import json
import logging
import os
from pathlib import Path

from aiohttp import web

from game.engine import Game
from game.store import Store

log = logging.getLogger("legend")

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
STATIC = Path(__file__).parent / "static"
INGRESS_PROXY = "172.30.32.2"
DEV_MODE = os.environ.get("DEV_MODE") == "1"


def load_options():
    path = DATA_DIR / "options.json"
    if path.exists():
        try:
            return json.loads(path.read_text())
        except ValueError:
            log.warning("Could not parse %s, using defaults", path)
    return {}


def identify(request):
    """Return (user_id, display_name) or raise 403."""
    if DEV_MODE:
        # Local testing: pick a player with ?user=Name in the page URL.
        user = request.query.get("user", "Player")
        return request.headers.get("X-Remote-User-Id") or "dev-" + user, user
    if request.remote != INGRESS_PROXY:
        raise web.HTTPForbidden(text="Legend of Darkness is only reachable through Home Assistant.")
    uid = request.headers.get("X-Remote-User-Id")
    if not uid:
        raise web.HTTPForbidden(text="No Home Assistant user supplied.")
    name = (request.headers.get("X-Remote-User-Display-Name")
            or request.headers.get("X-Remote-User-Name") or "")
    return uid, name


async def index(request):
    identify(request)
    return web.FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})


async def state(request):
    uid, name = identify(request)
    return web.json_response(request.app["game"].view(uid, name))


async def action(request):
    uid, name = identify(request)
    try:
        body = await request.json()
    except ValueError:
        raise web.HTTPBadRequest(text="Expected JSON")
    act = str(body.get("action", ""))[:120]
    value = body.get("value")
    value = None if value is None else str(value)[:300]
    return web.json_response(request.app["game"].act(uid, act, value, name))


def make_app(game):
    app = web.Application(client_max_size=16 * 1024)
    app["game"] = game
    app.router.add_get("/", index)
    app.router.add_get("/api/state", state)
    app.router.add_post("/api/action", action)
    app.router.add_static("/static/", STATIC)
    return app


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    options = load_options()
    game = Game(Store(str(DATA_DIR / "legend.db")), options)
    log.info("Legend of Darkness starting with options %s", game.opt)
    web.run_app(make_app(game), host="0.0.0.0", port=int(os.environ.get("PORT", 8099)),
                access_log=None)


if __name__ == "__main__":
    main()
