"""Tests for the AI-style program generator (v3.1.2)."""
import random

import pytest

from aceest.ai_program import EXERCISE_POOL, LEVELS, focus_for, generate_program
from aceest.validation import ValidationError


@pytest.mark.parametrize("code,focus", [
    ("FL", "Conditioning"), ("FL5", "Conditioning"), ("MG", "Hypertrophy"), ("BG", "Full Body"),
])
def test_focus_depends_on_program(code, focus):
    assert focus_for(code) == focus


@pytest.mark.parametrize("experience,days,per_day", [
    ("beginner", 3, 3), ("intermediate", 4, 4), ("advanced", 5, 4),
])
def test_plan_shape_matches_experience(experience, days, per_day):
    plan = generate_program("MG", experience, rng=random.Random(1))
    assert len({row["day"] for row in plan}) == days
    assert len(plan) == days * per_day


@pytest.mark.parametrize("experience", list(LEVELS))
def test_sets_and_reps_within_level_ranges(experience):
    (min_sets, max_sets), (min_reps, max_reps), _ = LEVELS[experience]
    for row in generate_program("FL", experience, rng=random.Random(7)):
        assert min_sets <= row["sets"] <= max_sets
        assert min_reps <= row["reps"] <= max_reps


def test_exercises_come_from_focus_pool_without_repeats_per_day():
    plan = generate_program("FL", "advanced", rng=random.Random(3))
    for day in {row["day"] for row in plan}:
        exercises = [r["exercise"] for r in plan if r["day"] == day]
        assert len(exercises) == len(set(exercises))
        assert set(exercises) <= set(EXERCISE_POOL["Conditioning"])


def test_same_seed_gives_same_plan():
    assert generate_program("BG", "beginner", random.Random(42)) == \
        generate_program("BG", "beginner", random.Random(42))


def test_experience_is_case_insensitive():
    assert generate_program("BG", "Beginner", random.Random(1))


def test_default_rng_is_used_when_not_given():
    assert len(generate_program("BG", "beginner")) == 9


def test_invalid_experience_raises():
    with pytest.raises(ValidationError):
        generate_program("FL", "expert")


# ---------- API ----------

def test_ai_program_endpoint(client, make_client, admin_headers):
    make_client("Arun", program="MG")
    response = client.post("/api/clients/Arun/ai-program",
                           json={"experience": "intermediate"}, headers=admin_headers)
    assert response.status_code == 200
    body = response.get_json()
    assert body["focus"] == "Hypertrophy"
    assert body["days_per_week"] == 4
    assert len(body["plan"]) == 16


def test_ai_program_requires_login(client, make_client):
    make_client("Bala")
    response = client.post("/api/clients/Bala/ai-program", json={"experience": "beginner"})
    assert response.status_code == 401


@pytest.mark.parametrize("payload", [{}, {"experience": "expert"}])
def test_ai_program_invalid_experience(client, make_client, admin_headers, payload):
    make_client("Chitra")
    response = client.post("/api/clients/Chitra/ai-program", json=payload, headers=admin_headers)
    assert response.status_code == 400


def test_ai_program_unknown_client(client, admin_headers):
    response = client.post("/api/clients/Ghost/ai-program",
                           json={"experience": "beginner"}, headers=admin_headers)
    assert response.status_code == 404
