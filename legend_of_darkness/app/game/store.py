"""SQLite persistence for players, news and village chatter."""

import json
import sqlite3
import time


class Store:
    def __init__(self, path):
        self.db = sqlite3.connect(path, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(
            """
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS players (
                id TEXT PRIMARY KEY,
                name TEXT UNIQUE COLLATE NOCASE,
                data TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                day TEXT NOT NULL,
                ts REAL NOT NULL,
                text TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS news_day ON news(day);
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS chatter (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                place TEXT NOT NULL,
                ts REAL NOT NULL,
                author TEXT NOT NULL,
                text TEXT NOT NULL
            );
            """
        )

    # players -------------------------------------------------------------

    def get_player(self, pid):
        row = self.db.execute("SELECT data FROM players WHERE id=?", (pid,)).fetchone()
        return json.loads(row["data"]) if row else None

    def save_player(self, p):
        self.db.execute(
            "INSERT INTO players(id, name, data) VALUES(?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET name=excluded.name, data=excluded.data",
            (p["id"], p.get("name"), json.dumps(p)),
        )

    def name_taken(self, name, pid):
        row = self.db.execute(
            "SELECT id FROM players WHERE name=? AND id<>?", (name, pid)
        ).fetchone()
        return row is not None

    def delete_player(self, pid):
        self.db.execute("DELETE FROM players WHERE id=?", (pid,))

    def all_players(self):
        rows = self.db.execute("SELECT data FROM players WHERE name IS NOT NULL").fetchall()
        return [json.loads(r["data"]) for r in rows]

    # news ----------------------------------------------------------------

    def add_news(self, day, text):
        self.db.execute(
            "INSERT INTO news(day, ts, text) VALUES(?,?,?)", (day, time.time(), text)
        )

    def news_days(self):
        rows = self.db.execute(
            "SELECT day FROM news GROUP BY day ORDER BY MAX(id) DESC"
        ).fetchall()
        return [r["day"] for r in rows]

    def news_for(self, day, limit=50):
        rows = self.db.execute(
            "SELECT text FROM news WHERE day=? ORDER BY id DESC LIMIT ?", (day, limit)
        ).fetchall()
        return [r["text"] for r in rows]

    def recent_news(self, limit=5):
        rows = self.db.execute(
            "SELECT text FROM news ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [r["text"] for r in rows]

    # settings ------------------------------------------------------------

    def get_settings(self):
        rows = self.db.execute("SELECT key, value FROM settings").fetchall()
        return {r["key"]: json.loads(r["value"]) for r in rows}

    def set_setting(self, key, value):
        self.db.execute(
            "INSERT INTO settings(key, value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, json.dumps(value)),
        )

    def clear_settings(self):
        self.db.execute("DELETE FROM settings")

    # chatter -------------------------------------------------------------

    def clear_chatter(self):
        self.db.execute("DELETE FROM chatter")

    def add_chatter(self, place, author, text):
        self.db.execute(
            "INSERT INTO chatter(place, ts, author, text) VALUES(?,?,?,?)",
            (place, time.time(), author, text),
        )
        self.db.execute(
            "DELETE FROM chatter WHERE place=? AND id NOT IN "
            "(SELECT id FROM chatter WHERE place=? ORDER BY id DESC LIMIT 200)",
            (place, place),
        )

    def chatter(self, place, limit=10):
        rows = self.db.execute(
            "SELECT author, text FROM chatter WHERE place=? ORDER BY id DESC LIMIT ?",
            (place, limit),
        ).fetchall()
        return [(r["author"], r["text"]) for r in rows][::-1]
