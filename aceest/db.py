"""SQLite persistence.

v2.0.1 - clients + weekly progress (Aceestver-2.0.1)
v2.2.4 - extended client profile, workouts, exercises and body metrics (Aceestver-2.2.4)

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
    """
    CREATE TABLE IF NOT EXISTS workouts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_name TEXT NOT NULL,
        date TEXT NOT NULL,
        workout_type TEXT NOT NULL,
        duration_min INTEGER,
        notes TEXT DEFAULT ''
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS exercises (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        workout_id INTEGER NOT NULL REFERENCES workouts(id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        sets INTEGER,
        reps INTEGER,
        weight REAL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_name TEXT NOT NULL,
        date TEXT NOT NULL,
        weight REAL,
        waist REAL,
        bodyfat REAL
    )
    """,
]

# Columns added to existing tables after their first release.
# Older databases are upgraded in place (no data loss, unlike the desktop
# app which dropped and recreated the clients table).
# Each entry: (table, column, DDL). DDL is a literal - no SQL string formatting.
MIGRATIONS = [
    ("clients", "height", "ALTER TABLE clients ADD COLUMN height REAL"),
    ("clients", "target_weight", "ALTER TABLE clients ADD COLUMN target_weight REAL"),
    ("clients", "target_adherence", "ALTER TABLE clients ADD COLUMN target_adherence INTEGER"),
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


def existing_columns(db, table):
    rows = db.execute("SELECT name FROM pragma_table_info(?)", (table,)).fetchall()
    return {row["name"] for row in rows}


def migrate(db):
    """Add any missing columns listed in MIGRATIONS. Returns the columns added."""
    added = []
    for table, column, ddl in MIGRATIONS:
        if column not in existing_columns(db, table):
            db.execute(ddl)
            added.append(f"{table}.{column}")
    return added


def init_db():
    db = get_db()
    for statement in SCHEMA:
        db.execute(statement)
    migrate(db)
    db.commit()


def init_app(app):
    directory = os.path.dirname(os.path.abspath(app.config["DATABASE"]))
    os.makedirs(directory, exist_ok=True)
    app.teardown_appcontext(close_db)
    with app.app_context():
        init_db()
