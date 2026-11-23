"""Tests for authentication (v3.1.2)."""
import pytest
from itsdangerous import URLSafeTimedSerializer

from aceest import create_app
from aceest.auth import TOKEN_SALT
from aceest.db import get_db
from tests.conftest import ADMIN_PASSWORD, make_config


def test_admin_can_log_in(client):
    response = client.post("/api/auth/login",
                           json={"username": "admin", "password": ADMIN_PASSWORD})
    assert response.status_code == 200
    body = response.get_json()
    assert body["role"] == "Admin"
    assert body["token"]
    assert body["expires_in"] == 8 * 3600


@pytest.mark.parametrize("payload", [
    {"username": "admin", "password": "wrong"},
    {"username": "nobody", "password": ADMIN_PASSWORD},
    {"username": "admin"},
    {},
])
def test_invalid_credentials_are_rejected(client, payload):
    response = client.post("/api/auth/login", json=payload)
    assert response.status_code == 401
    assert response.get_json()["error"] == "Invalid credentials"


def test_password_is_stored_hashed(app):
    with app.app_context():
        stored = get_db().execute(
            "SELECT password_hash FROM users WHERE username = 'admin'").fetchone()[0]
    assert ADMIN_PASSWORD not in stored
    assert stored.startswith("pbkdf2:sha256")


def test_admin_is_created_only_once(tmp_path):
    config = make_config(tmp_path)
    create_app(config)
    app = create_app(config)  # restart with the same database
    with app.app_context():
        assert get_db().execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1


def test_random_admin_password_generated_when_not_configured(tmp_path, caplog):
    caplog.set_level("WARNING")
    app = create_app(make_config(tmp_path, ADMIN_PASSWORD=None))
    assert any("generated admin password" in r.getMessage() for r in caplog.records)
    # the documented default from the desktop app must NOT work
    response = app.test_client().post("/api/auth/login",
                                      json={"username": "admin", "password": "admin"})
    assert response.status_code == 401


def test_random_secret_key_when_not_configured(tmp_path, caplog):
    caplog.set_level("WARNING")
    app = create_app(make_config(tmp_path, SECRET_KEY=None))
    assert app.config["SECRET_KEY"]
    assert any("ACEEST_SECRET_KEY not set" in r.getMessage() for r in caplog.records)


# ---------- token handling ----------

def test_me_returns_current_user(client, admin_headers):
    assert client.get("/api/auth/me", headers=admin_headers).get_json() == {
        "username": "admin", "role": "Admin"}


def test_me_requires_token(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.get_json()["error"] == "Authentication required"


@pytest.mark.parametrize("header", ["Bearer not-a-token", "Bearer ", "Basic abc", "token"])
def test_malformed_tokens_are_rejected(client, header):
    assert client.get("/api/auth/me", headers={"Authorization": header}).status_code == 401


def test_token_signed_with_other_key_is_rejected(client):
    forged = URLSafeTimedSerializer("attacker-key", salt=TOKEN_SALT).dumps(
        {"u": "admin", "r": "Admin"})
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {forged}"})
    assert response.status_code == 401
    assert response.get_json()["error"] == "Invalid token"


def test_expired_token_is_rejected(tmp_path):
    app = create_app(make_config(tmp_path, TOKEN_MAX_AGE=-1))
    client = app.test_client()
    token = client.post("/api/auth/login", json={
        "username": "admin", "password": ADMIN_PASSWORD}).get_json()["token"]
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert "expired" in response.get_json()["error"]


def test_token_is_valid_on_another_replica_with_same_secret(tmp_path):
    """Two pods sharing ACEEST_SECRET_KEY accept each other's tokens."""
    pod_a = create_app(make_config(tmp_path / "a")).test_client()
    pod_b = create_app(make_config(tmp_path / "b")).test_client()
    token = pod_a.post("/api/auth/login", json={
        "username": "admin", "password": ADMIN_PASSWORD}).get_json()["token"]
    assert pod_b.get("/api/auth/me",
                     headers={"Authorization": f"Bearer {token}"}).status_code == 200
