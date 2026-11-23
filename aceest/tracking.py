"""Workout logging, body metrics, BMI and client summary (ported from Aceestver-2.2.4)."""
from datetime import date

from flask import Blueprint, jsonify, request

from .clients import _client_row, _error
from .db import get_db
from .programs import PROGRAMS, estimate_calories
from .validation import (
    COUNT_RANGE, DURATION_RANGE, PERCENT_RANGE, WEIGHT_RANGE,
    ValidationError, iso_date, json_body, number, text,
)

bp = Blueprint("tracking", __name__, url_prefix="/api/clients")


# ---------- BMI ----------

BMI_CATEGORIES = [
    (18.5, "Underweight", "Potential nutrient deficiency, low energy."),
    (25.0, "Normal", "Low risk if active and strong."),
    (30.0, "Overweight", "Moderate risk; focus on adherence and progressive activity."),
    (float("inf"), "Obese", "Higher risk; prioritize fat loss, consistency, and supervision."),
]


def calculate_bmi(weight_kg, height_cm):
    height_m = height_cm / 100.0
    return round(weight_kg / (height_m * height_m), 1)


def bmi_category(bmi):
    """Return (category, risk note) using the same thresholds as the desktop app."""
    for upper_bound, category, risk in BMI_CATEGORIES:
        if bmi < upper_bound:
            return category, risk
    return BMI_CATEGORIES[-1][1], BMI_CATEGORIES[-1][2]  # pragma: no cover - unreachable


# ---------- workouts ----------

def _parse_exercises(raw):
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValidationError("'exercises' must be a list")
    exercises = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValidationError("each exercise must be an object")
        exercises.append({
            "name": text(item, "name", required=True),
            "sets": number(item, "sets", int, default=0, **COUNT_RANGE),
            "reps": number(item, "reps", int, default=0, **COUNT_RANGE),
            "weight": number(item, "weight", float, default=0.0, **WEIGHT_RANGE),
        })
    return exercises


def _workouts_for(name):
    db = get_db()
    workouts = []
    rows = db.execute(
        "SELECT * FROM workouts WHERE client_name = ? ORDER BY date DESC, id DESC", (name,)
    ).fetchall()
    for row in rows:
        workout = dict(row)
        workout.pop("client_name")
        workout["exercises"] = [
            {k: ex[k] for k in ("name", "sets", "reps", "weight")}
            for ex in db.execute(
                "SELECT * FROM exercises WHERE workout_id = ? ORDER BY id", (row["id"],)
            )
        ]
        workouts.append(workout)
    return workouts


@bp.post("/<name>/workouts")
def log_workout(name):
    if _client_row(name) is None:
        return _error("Client not found", 404)
    data = json_body(request)
    workout_date = iso_date(data, "date", default=date.today().isoformat())
    workout_type = text(data, "workout_type", required=True, max_length=50)
    duration = number(data, "duration_min", int, default=60, **DURATION_RANGE)
    notes = text(data, "notes", max_length=500)
    exercises = _parse_exercises(data.get("exercises"))

    db = get_db()
    cursor = db.execute(
        "INSERT INTO workouts (client_name, date, workout_type, duration_min, notes) "
        "VALUES (?, ?, ?, ?, ?)",
        (name, workout_date, workout_type, duration, notes),
    )
    workout_id = cursor.lastrowid
    db.executemany(
        "INSERT INTO exercises (workout_id, name, sets, reps, weight) VALUES (?, ?, ?, ?, ?)",
        [(workout_id, e["name"], e["sets"], e["reps"], e["weight"]) for e in exercises],
    )
    db.commit()
    return jsonify(message="Workout logged successfully", id=workout_id, date=workout_date,
                   workout_type=workout_type, exercises=len(exercises)), 201


@bp.get("/<name>/workouts")
def workout_history(name):
    if _client_row(name) is None:
        return _error("Client not found", 404)
    workouts = _workouts_for(name)
    return jsonify(client=name, count=len(workouts), workouts=workouts)


# ---------- body metrics ----------

@bp.post("/<name>/metrics")
def log_metrics(name):
    client = _client_row(name)
    if client is None:
        return _error("Client not found", 404)
    data = json_body(request)
    metric_date = iso_date(data, "date", default=date.today().isoformat())
    weight = number(data, "weight", float, **WEIGHT_RANGE)
    waist = number(data, "waist", float, minimum=0, maximum=300)
    bodyfat = number(data, "bodyfat", float, **PERCENT_RANGE)
    if weight is None and waist is None and bodyfat is None:
        raise ValidationError("provide at least one of weight, waist or bodyfat")

    db = get_db()
    db.execute(
        "INSERT INTO metrics (client_name, date, weight, waist, bodyfat) VALUES (?, ?, ?, ?, ?)",
        (name, metric_date, weight, waist, bodyfat),
    )
    if weight:  # keep the profile weight (and calorie target) in sync, like the desktop app
        db.execute(
            "UPDATE clients SET weight = ?, calories = ? WHERE name = ?",
            (weight, estimate_calories(weight, client["program"]), name),
        )
    db.commit()
    return jsonify(message="Metrics logged successfully", date=metric_date), 201


@bp.get("/<name>/metrics")
def metrics_history(name):
    """Body metrics in date order (data for the weight trend chart)."""
    if _client_row(name) is None:
        return _error("Client not found", 404)
    rows = get_db().execute(
        "SELECT date, weight, waist, bodyfat FROM metrics WHERE client_name = ? "
        "ORDER BY date, id",
        (name,),
    ).fetchall()
    return jsonify(client=name, metrics=[dict(r) for r in rows])


@bp.get("/<name>/bmi")
def bmi_info(name):
    client = _client_row(name)
    if client is None:
        return _error("Client not found", 404)
    if not client["height"] or not client["weight"]:
        return _error("Enter valid height and weight first")
    bmi = calculate_bmi(client["weight"], client["height"])
    category, risk = bmi_category(bmi)
    return jsonify(client=name, bmi=bmi, category=category, risk=risk)


# ---------- summary ----------

@bp.get("/<name>/summary")
def client_summary(name):
    client = _client_row(name)
    if client is None:
        return _error("Client not found", 404)
    db = get_db()
    weeks, avg = db.execute(
        "SELECT COUNT(*), AVG(adherence) FROM progress WHERE client_name = ?", (name,)
    ).fetchone()
    last_metric = db.execute(
        "SELECT date, weight, waist, bodyfat FROM metrics WHERE client_name = ? "
        "ORDER BY date DESC, id DESC LIMIT 1",
        (name,),
    ).fetchone()
    workouts = db.execute(
        "SELECT COUNT(*), COALESCE(SUM(duration_min), 0) FROM workouts WHERE client_name = ?",
        (name,),
    ).fetchone()
    program = PROGRAMS.get(client["program"], {})
    return jsonify(
        profile={k: client[k] for k in ("name", "age", "height", "weight", "program", "calories")},
        program_notes=program.get("desc", ""),
        goals={
            "target_weight": client["target_weight"],
            "target_adherence": client["target_adherence"],
        },
        progress={"weeks_logged": weeks, "average_adherence": round(avg, 1) if avg else 0},
        workouts={"sessions": workouts[0], "total_minutes": workouts[1]},
        last_body_metrics=dict(last_metric) if last_metric else None,
    )
