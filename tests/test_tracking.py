"""Tests for workouts, body metrics, BMI and summary (v2.2.4)."""
from datetime import date

import pytest

from aceest.tracking import bmi_category, calculate_bmi


# ---------- BMI (pure functions) ----------

@pytest.mark.parametrize("weight,height,expected", [
    (70, 175, 22.9), (50, 170, 17.3), (90, 180, 27.8), (120, 170, 41.5),
])
def test_calculate_bmi(weight, height, expected):
    assert calculate_bmi(weight, height) == expected


@pytest.mark.parametrize("bmi,category", [
    (16.0, "Underweight"), (18.4, "Underweight"),
    (18.5, "Normal"), (24.9, "Normal"),
    (25.0, "Overweight"), (29.9, "Overweight"),
    (30.0, "Obese"), (45.0, "Obese"),
])
def test_bmi_category_thresholds(bmi, category):
    assert bmi_category(bmi)[0] == category


def test_bmi_endpoint(client, make_client):
    make_client("Arun", weight=70, height=175)
    data = client.get("/api/clients/Arun/bmi").get_json()
    assert data["bmi"] == 22.9
    assert data["category"] == "Normal"
    assert data["risk"]


def test_bmi_requires_height_and_weight(client, make_client):
    make_client("Bala", weight=70)  # no height
    response = client.get("/api/clients/Bala/bmi")
    assert response.status_code == 400
    assert "height and weight" in response.get_json()["error"]


# ---------- extended profile ----------

def test_profile_stores_height_and_goals(client, make_client):
    make_client("Chitra", height=160, target_weight=55, target_adherence=85)
    data = client.get("/api/clients/Chitra").get_json()
    assert data["height"] == 160
    assert data["target_weight"] == 55
    assert data["target_adherence"] == 85


def test_height_out_of_range_rejected(client):
    response = client.post("/api/clients", json={"name": "Dev", "program": "FL", "height": 300})
    assert response.status_code == 400


def test_new_five_day_program_is_available(client, make_client):
    body = make_client("Esha", program="FL5", weight=60)
    assert body["client"]["calories"] == 60 * 24


# ---------- workouts ----------

def test_log_workout_with_exercises(client, make_client):
    make_client("Faiz")
    response = client.post("/api/clients/Faiz/workouts", json={
        "date": "2026-03-01", "workout_type": "Strength", "duration_min": 75,
        "notes": "felt strong",
        "exercises": [
            {"name": "Back Squat", "sets": 5, "reps": 5, "weight": 100},
            {"name": "Bench Press", "sets": 3, "reps": 8, "weight": 70},
        ],
    })
    assert response.status_code == 201
    assert response.get_json()["exercises"] == 2

    history = client.get("/api/clients/Faiz/workouts").get_json()
    assert history["count"] == 1
    workout = history["workouts"][0]
    assert workout["workout_type"] == "Strength"
    assert workout["duration_min"] == 75
    assert workout["exercises"][0] == {"name": "Back Squat", "sets": 5, "reps": 5, "weight": 100}


def test_workout_defaults_to_today(client, make_client):
    make_client("Gita")
    body = client.post("/api/clients/Gita/workouts", json={"workout_type": "Cardio"}).get_json()
    assert body["date"] == date.today().isoformat()


def test_workout_history_is_newest_first(client, make_client):
    make_client("Hari")
    for day in ("2026-01-01", "2026-01-03", "2026-01-02"):
        client.post("/api/clients/Hari/workouts", json={"date": day, "workout_type": "Mobility"})
    dates = [w["date"] for w in client.get("/api/clients/Hari/workouts").get_json()["workouts"]]
    assert dates == ["2026-01-03", "2026-01-02", "2026-01-01"]


@pytest.mark.parametrize("payload,message", [
    ({}, "workout_type"),
    ({"workout_type": "Strength", "date": "01-02-2026"}, "YYYY-MM-DD"),
    ({"workout_type": "Strength", "duration_min": 700}, "duration_min"),
    ({"workout_type": "Strength", "exercises": "squats"}, "must be a list"),
    ({"workout_type": "Strength", "exercises": ["squats"]}, "must be an object"),
    ({"workout_type": "Strength", "exercises": [{"sets": 3}]}, "'name' is required"),
    ({"workout_type": "Strength", "exercises": [{"name": "Row", "reps": -1}]}, "reps"),
])
def test_invalid_workouts_are_rejected(client, make_client, payload, message):
    make_client("Indu")
    response = client.post("/api/clients/Indu/workouts", json=payload)
    assert response.status_code == 400
    assert message in response.get_json()["error"]
    assert client.get("/api/clients/Indu/workouts").get_json()["count"] == 0


def test_workouts_for_unknown_client(client):
    assert client.post("/api/clients/Ghost/workouts",
                       json={"workout_type": "Cardio"}).status_code == 404
    assert client.get("/api/clients/Ghost/workouts").status_code == 404


# ---------- body metrics ----------

def test_log_metrics_and_history_in_date_order(client, make_client):
    make_client("Jai", weight=80)
    client.post("/api/clients/Jai/metrics", json={"date": "2026-02-10", "weight": 78})
    client.post("/api/clients/Jai/metrics",
                json={"date": "2026-02-01", "weight": 80, "waist": 90, "bodyfat": 22})
    metrics = client.get("/api/clients/Jai/metrics").get_json()["metrics"]
    assert [m["date"] for m in metrics] == ["2026-02-01", "2026-02-10"]
    assert metrics[0] == {"date": "2026-02-01", "weight": 80, "waist": 90, "bodyfat": 22}


def test_logging_weight_updates_profile_and_calories(client, make_client):
    make_client("Kavya", program="MG", weight=60)
    client.post("/api/clients/Kavya/metrics", json={"weight": 64})
    profile = client.get("/api/clients/Kavya").get_json()
    assert profile["weight"] == 64
    assert profile["calories"] == 64 * 35


def test_logging_only_waist_keeps_profile_weight(client, make_client):
    make_client("Lakshmi", weight=58)
    assert client.post("/api/clients/Lakshmi/metrics", json={"waist": 70}).status_code == 201
    assert client.get("/api/clients/Lakshmi").get_json()["weight"] == 58


@pytest.mark.parametrize("payload", [
    {}, {"date": "2026-02-01"}, {"bodyfat": 120}, {"weight": -1}, {"weight": 70, "date": "bad"},
])
def test_invalid_metrics_are_rejected(client, make_client, payload):
    make_client("Mani")
    assert client.post("/api/clients/Mani/metrics", json=payload).status_code == 400


def test_metrics_for_unknown_client(client):
    assert client.post("/api/clients/Ghost/metrics", json={"weight": 70}).status_code == 404
    assert client.get("/api/clients/Ghost/metrics").status_code == 404
    assert client.get("/api/clients/Ghost/bmi").status_code == 404


# ---------- summary ----------

def test_summary_for_new_client(client, make_client):
    make_client("Nila", program="BG", weight=55, height=158)
    data = client.get("/api/clients/Nila/summary").get_json()
    assert data["profile"]["program"] == "BG"
    assert data["program_notes"] == "3-day simple beginner full-body"
    assert data["progress"] == {"weeks_logged": 0, "average_adherence": 0}
    assert data["workouts"] == {"sessions": 0, "total_minutes": 0}
    assert data["last_body_metrics"] is None


def test_summary_aggregates_all_activity(client, make_client):
    make_client("Om", program="MG", weight=75, target_weight=80, target_adherence=90)
    client.post("/api/clients/Om/progress", json={"adherence": 80})
    client.post("/api/clients/Om/progress", json={"adherence": 90})
    client.post("/api/clients/Om/workouts", json={"workout_type": "Push", "duration_min": 60})
    client.post("/api/clients/Om/workouts", json={"workout_type": "Pull", "duration_min": 45})
    client.post("/api/clients/Om/metrics", json={"date": "2026-01-01", "weight": 74})
    client.post("/api/clients/Om/metrics", json={"date": "2026-02-01", "weight": 76})

    data = client.get("/api/clients/Om/summary").get_json()
    assert data["goals"] == {"target_weight": 80, "target_adherence": 90}
    assert data["progress"] == {"weeks_logged": 2, "average_adherence": 85.0}
    assert data["workouts"] == {"sessions": 2, "total_minutes": 105}
    assert data["last_body_metrics"]["date"] == "2026-02-01"
    assert data["profile"]["weight"] == 76


def test_summary_for_unknown_client(client):
    assert client.get("/api/clients/Ghost/summary").status_code == 404
