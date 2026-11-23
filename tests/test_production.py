"""Tests for v3.0.1 production features: readiness, headers, URL prefix, logging."""
import sqlite3

import pytest

from aceest import __version__, create_app
from aceest.db import get_db, migrate
from aceest.middleware import PrefixMiddleware


# ---------- probes ----------

def test_ready_when_database_reachable(client):
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ready", "version": __version__}


def test_not_ready_when_database_unavailable(app, tmp_path):
    app.config["DATABASE"] = str(tmp_path)  # a directory cannot be opened as a DB
    response = app.test_client().get("/ready")
    assert response.status_code == 503
    assert response.get_json()["status"] == "unavailable"


def test_health_does_not_depend_on_database(app, tmp_path):
    app.config["DATABASE"] = str(tmp_path)
    assert app.test_client().get("/health").status_code == 200


# ---------- deployment headers ----------

@pytest.mark.parametrize("path", ["/health", "/api/programs", "/api/unknown"])
def test_every_response_has_deployment_headers(client, path):
    response = client.get(path)
    assert response.headers["X-App-Version"] == __version__
    assert response.headers["X-Deployment-Track"] == "stable"
    assert response.headers["X-Served-By"]


def test_track_header_reflects_configuration(tmp_path):
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "t.db"),
                      "DEPLOYMENT_TRACK": "green"})
    assert app.test_client().get("/health").headers["X-Deployment-Track"] == "green"


# ---------- URL prefix middleware ----------

@pytest.fixture
def prefixed_client(tmp_path):
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "p.db"),
                      "URL_PREFIX": "/canary"})
    # URL_PREFIX from test_config is applied by create_app
    return app.test_client()


def test_prefixed_path_is_served(prefixed_client):
    response = prefixed_client.get("/canary/version")
    assert response.status_code == 200
    assert response.get_json()["version"] == __version__


def test_prefix_root_serves_dashboard(prefixed_client):
    assert prefixed_client.get("/canary").status_code == 200
    assert prefixed_client.get("/canary/").status_code == 200


def test_unprefixed_probe_still_works(prefixed_client):
    assert prefixed_client.get("/health").status_code == 200


def test_similar_prefix_is_not_stripped(prefixed_client):
    assert prefixed_client.get("/canaryX/version").status_code == 404


def test_prefixed_api_round_trip(prefixed_client):
    created = prefixed_client.post("/canary/api/clients", json={"name": "Arun", "program": "FL"})
    assert created.status_code == 201
    assert prefixed_client.get("/canary/api/clients/Arun").status_code == 200


@pytest.mark.parametrize("prefix,expected", [
    ("", ""), ("/", ""), ("canary", "/canary"), ("/canary/", "/canary"),
])
def test_prefix_is_normalised(prefix, expected):
    assert PrefixMiddleware(None, prefix).prefix == expected


def test_middleware_sets_script_name():
    seen = {}

    def fake_app(environ, start_response):
        seen.update(environ)
        return []

    PrefixMiddleware(fake_app, "/ab")({"PATH_INFO": "/ab/api/programs"}, None)
    assert seen["SCRIPT_NAME"] == "/ab"
    assert seen["PATH_INFO"] == "/api/programs"


# ---------- schema race fix ----------

def test_fresh_database_has_full_schema_without_migration(app):
    with app.app_context():
        assert migrate(get_db()) == []


def test_concurrent_migration_duplicate_column_is_ignored(app, monkeypatch):
    """Simulate another worker adding the column between our check and ALTER TABLE."""
    import aceest.db as db_module

    monkeypatch.setattr(db_module, "existing_columns", lambda db, table: set())
    with app.app_context():
        assert migrate(get_db()) == []  # every ALTER hits 'duplicate column' -> skipped


def test_other_migration_errors_are_raised(app, monkeypatch):
    import aceest.db as db_module

    monkeypatch.setattr(db_module, "existing_columns", lambda db, table: set())
    monkeypatch.setattr(db_module, "MIGRATIONS",
                        [("missing_table", "x", "ALTER TABLE missing_table ADD COLUMN x INT")])
    with app.app_context(), pytest.raises(sqlite3.OperationalError):
        migrate(get_db())


# ---------- logging ----------

def test_non_testing_app_configures_logging(tmp_path, caplog):
    caplog.set_level("INFO")
    create_app({"DATABASE": str(tmp_path / "log.db")})
    assert any("started" in r.getMessage() for r in caplog.records)
