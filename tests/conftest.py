"""Shared pytest fixtures.

Every test gets a fresh application backed by its own temporary SQLite file,
so tests are isolated and can run in any order (locally, in Jenkins or in Docker).
"""
import pytest

from aceest import create_app


@pytest.fixture
def app(tmp_path):
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "test.db")})
    yield app


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
