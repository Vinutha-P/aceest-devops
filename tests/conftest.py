"""Shared pytest fixtures.

Every test gets a fresh application backed by its own temporary SQLite file,
so tests are isolated and can run in any order (locally, in Jenkins or in Docker).
"""
import pytest

from aceest import create_app

ADMIN_PASSWORD = "test-admin-password"


def make_config(tmp_path, **overrides):
    config = {
        "TESTING": True,
        "DATABASE": str(tmp_path / "test.db"),
        "SECRET_KEY": "test-secret-key",
        "ADMIN_PASSWORD": ADMIN_PASSWORD,
        # fast hashing keeps the suite quick; production uses scrypt (the default)
        "PASSWORD_HASH_METHOD": "pbkdf2:sha256:1000",
    }
    config.update(overrides)
    return config


@pytest.fixture
def app(tmp_path):
    yield create_app(make_config(tmp_path))


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def make_client(client):
    """Helper that creates a client through the API and returns the response JSON."""

    def _make(name="Arun", program="FL", **fields):
        payload = {"name": name, "program": program, "age": 30, "weight": 70}
        payload.update(fields)
        response = client.post("/api/clients", json=payload)
        assert response.status_code in (200, 201), response.get_json()
        return response.get_json()

    return _make


@pytest.fixture
def login(client):
    """Log in and return the Authorization header."""

    def _login(username="admin", password=ADMIN_PASSWORD):
        response = client.post("/api/auth/login",
                               json={"username": username, "password": password})
        assert response.status_code == 200, response.get_json()
        return {"Authorization": f"Bearer {response.get_json()['token']}"}

    return _login


@pytest.fixture
def admin_headers(login):
    return login()
