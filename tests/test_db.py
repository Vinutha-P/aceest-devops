"""Tests for the database layer and schema migration (v2.0.1 / v2.2.4)."""
import sqlite3

from aceest import create_app
from aceest.db import existing_columns, get_db, migrate


def test_all_tables_are_created(app):
    with app.app_context():
        tables = {r["name"] for r in get_db().execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"clients", "progress", "workouts", "exercises", "metrics"} <= tables


def test_connection_is_reused_within_a_request(app):
    with app.app_context():
        assert get_db() is get_db()


def test_database_directory_is_created(tmp_path):
    db_path = tmp_path / "nested" / "dir" / "aceest.db"
    create_app({"TESTING": True, "DATABASE": str(db_path)})
    assert db_path.exists()


def test_old_v2_0_database_is_upgraded_without_data_loss(tmp_path):
    """A database created by v2.0.1 (no height/goal columns) is migrated in place."""
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE clients (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE "
                 "NOT NULL, age INTEGER, weight REAL, program TEXT, calories INTEGER, "
                 "notes TEXT DEFAULT '')")
    conn.execute("INSERT INTO clients (name, age, weight, program, calories) "
                 "VALUES ('Legacy', 40, 82, 'FL', 1804)")
    conn.commit()
    conn.close()

    app = create_app({"TESTING": True, "DATABASE": str(db_path)})
    client = app.test_client()
    data = client.get("/api/clients/Legacy").get_json()
    assert data["calories"] == 1804           # old data kept
    assert data["height"] is None             # new column present
    assert client.post("/api/clients", json={"name": "Legacy", "program": "FL",
                                             "height": 170}).status_code == 200


def test_migrate_is_idempotent(app):
    with app.app_context():
        db = get_db()
        assert migrate(db) == []  # already up to date
        assert {"height", "target_weight", "target_adherence"} <= existing_columns(db, "clients")
