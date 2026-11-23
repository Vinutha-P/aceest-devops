"""Tests for the program catalogue API."""
import pytest

from aceest.programs import PROGRAMS


def test_list_programs_returns_all_codes(client):
    data = client.get("/api/programs").get_json()
    codes = {p["code"] for p in data["programs"]}
    assert codes == set(PROGRAMS)
    assert data["site_metrics"]["capacity_users"] == 150


@pytest.mark.parametrize("code", ["FL", "MG", "BG"])
def test_program_detail_has_workout_and_diet(client, code):
    response = client.get(f"/api/programs/{code}")
    assert response.status_code == 200
    data = response.get_json()
    assert data["code"] == code
    assert data["workout"] and data["diet"]
    assert data["color"].startswith("#")


def test_program_code_is_case_insensitive(client):
    assert client.get("/api/programs/fl").get_json()["code"] == "FL"


def test_unknown_program_returns_404(client):
    assert client.get("/api/programs/XYZ").status_code == 404
