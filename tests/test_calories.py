"""Tests for calorie estimation (v1.1)."""
import pytest

from aceest.programs import PROGRAMS, estimate_calories


@pytest.mark.parametrize("code,weight,expected", [
    ("FL", 70, 1540),
    ("MG", 80, 2800),
    ("BG", 60.5, 1573),
])
def test_estimate_calories_uses_program_factor(code, weight, expected):
    assert estimate_calories(weight, code) == expected


def test_every_program_has_a_calorie_factor():
    assert all(p["calorie_factor"] > 0 for p in PROGRAMS.values())


def test_calorie_endpoint(client):
    data = client.get("/api/programs/mg/calories?weight=80").get_json()
    assert data == {
        "program": "Muscle Gain (MG) - PPL",
        "weight": 80.0,
        "calorie_factor": 35,
        "calories": 2800,
    }


@pytest.mark.parametrize("query", ["", "?weight=abc", "?weight=0", "?weight=-5"])
def test_calorie_endpoint_rejects_bad_weight(client, query):
    assert client.get(f"/api/programs/FL/calories{query}").status_code == 400


def test_calorie_endpoint_unknown_program(client):
    assert client.get("/api/programs/ZZ/calories?weight=70").status_code == 404
