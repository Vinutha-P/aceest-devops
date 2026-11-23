"""Tests for the dashboard, health and version endpoints."""
from aceest import __version__


def test_health_returns_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_version_reports_app_version_and_track(client):
    data = client.get("/version").get_json()
    assert data["version"] == __version__
    assert data["track"] == "stable"
    assert data["pod"]


def test_deployment_track_comes_from_config():
    from aceest import create_app

    app = create_app({"TESTING": True, "DEPLOYMENT_TRACK": "canary"})
    assert app.test_client().get("/version").get_json()["track"] == "canary"


def test_dashboard_renders_programs(client):
    response = client.get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "ACEest FUNCTIONAL FITNESS" in html
    assert "Muscle Gain (MG)" in html
    assert f"v{__version__}" in html
