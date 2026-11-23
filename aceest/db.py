"""SQLite persistence (introduced in v2.0.1, ported from Aceestver-2.0.1).

One connection per request is stored on ``flask.g`` and closed on teardown.
The database path comes from ``app.config["DATABASE"]`` (env var ``ACEEST_DB``).
"""
import os
import sqlite3

from flask import current_app, g

SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS clients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        age INTEGER,
        weight REAL,
        program TEXT,
        calories INTEGER,
        notes TEXT DEFAULT ''
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS progress (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_name TEXT NOT NULL,
        week TEXT NOT NULL,
        adherence INTEGER NOT NULL
    )
    """,
]


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    for statement in SCHEMA:
        db.execute(statement)
    db.commit()


def init_app(app):
    directory = os.path.dirname(os.path.abspath(app.config["DATABASE"]))
    os.makedirs(directory, exist_ok=True)
    app.teardown_appcontext(close_db)
    with app.app_context():
        init_db()
