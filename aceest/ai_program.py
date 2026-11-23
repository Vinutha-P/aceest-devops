"""AI-style workout program generator (ported from Aceestver-3.1.2)."""
import random

from flask import Blueprint, jsonify, request

from .auth import login_required
from .clients import _client_row, _error
from .validation import ValidationError, json_body, text

bp = Blueprint("ai_program", __name__, url_prefix="/api/clients")

EXERCISE_POOL = {
    "Strength": ["Squat", "Deadlift", "Bench Press", "Overhead Press", "Pull-Up", "Barbell Row"],
    "Hypertrophy": ["Leg Press", "Incline Dumbbell Press", "Lat Pulldown", "Lateral Raise",
                    "Bicep Curl", "Tricep Extension"],
    "Conditioning": ["Running", "Cycling", "Rowing", "Burpees", "Jump Rope",
                     "Kettlebell Swings"],
    "Full Body": ["Push-Up", "Pull-Up", "Lunge", "Plank", "Dumbbell Row", "Dumbbell Press"],
}

# experience -> (sets range, reps range, training days per week)
LEVELS = {
    "beginner": ((2, 3), (8, 12), 3),
    "intermediate": ((3, 4), (8, 15), 4),
    "advanced": ((4, 5), (6, 15), 5),
}

WEEK_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]


def focus_for(program_code):
    if program_code in ("FL", "FL5"):
        return "Conditioning"
    if program_code == "MG":
        return "Hypertrophy"
    return "Full Body"


def generate_program(program_code, experience, rng=None):
    """Return a weekly plan: list of {day, exercise, sets, reps}.

    ``rng`` can be injected (e.g. random.Random(42)) for reproducible tests.
    """
    experience = experience.lower()
    if experience not in LEVELS:
        raise ValidationError("experience must be beginner, intermediate or advanced")
    rng = rng or random.SystemRandom()
    sets_range, reps_range, days = LEVELS[experience]
    pool = EXERCISE_POOL[focus_for(program_code)]
    per_day = 3 if days < 4 else 4

    plan = []
    for day in WEEK_DAYS[:days]:
        for exercise in rng.sample(pool, k=per_day):
            plan.append({
                "day": day,
                "exercise": exercise,
                "sets": rng.randint(*sets_range),
                "reps": rng.randint(*reps_range),
            })
    return plan


@bp.post("/<name>/ai-program")
@login_required()
def ai_program(name):
    client = _client_row(name)
    if client is None:
        return _error("Client not found", 404)
    experience = text(json_body(request), "experience", required=True, max_length=20)
    plan = generate_program(client["program"], experience)
    return jsonify(
        client=name,
        program=client["program"],
        focus=focus_for(client["program"]),
        experience=experience.lower(),
        days_per_week=LEVELS[experience.lower()][2],
        plan=plan,
    )
