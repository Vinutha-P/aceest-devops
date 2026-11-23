"""Training program catalogue (Aceestver-1.0) with calorie factors (Aceestver-1.1)."""
from flask import Blueprint, abort, jsonify, request

PROGRAMS = {
    "FL": {
        "name": "Fat Loss (FL)",
        "workout": [
            "Mon: Back Squat 5x5 + Core",
            "Tue: EMOM 20min Assault Bike",
            "Wed: Bench Press + 21-15-9",
            "Thu: Deadlift + Box Jumps",
            "Fri: Zone 2 Cardio 30min",
        ],
        "diet": [
            "Breakfast: Egg Whites + Oats",
            "Lunch: Grilled Chicken + Brown Rice",
            "Dinner: Fish Curry + Millet Roti",
            "Target: ~2000 kcal",
        ],
        "color": "#e74c3c",
        "calorie_factor": 22,
    },
    "MG": {
        "name": "Muscle Gain (MG)",
        "workout": [
            "Mon: Squat 5x5",
            "Tue: Bench 5x5",
            "Wed: Deadlift 4x6",
            "Thu: Front Squat 4x8",
            "Fri: Incline Press 4x10",
            "Sat: Barbell Rows 4x10",
        ],
        "diet": [
            "Breakfast: Eggs + Peanut Butter Oats",
            "Lunch: Chicken Biryani",
            "Dinner: Mutton Curry + Rice",
            "Target: ~3200 kcal",
        ],
        "color": "#2ecc71",
        "calorie_factor": 35,
    },
    "BG": {
        "name": "Beginner (BG)",
        "workout": [
            "Full Body Circuit: Air Squats, Ring Rows, Push-ups",
            "Focus: Technique & Consistency",
        ],
        "diet": [
            "Balanced Tamil Meals",
            "Idli / Dosa / Rice + Dal",
            "Protein Target: 120g/day",
        ],
        "color": "#3498db",
        "calorie_factor": 26,
    },
}

SITE_METRICS = {"capacity_users": 150, "area_sq_ft": 10000, "break_even_members": 250}

bp = Blueprint("programs", __name__, url_prefix="/api/programs")


def estimate_calories(weight_kg, code):
    """Daily calorie estimate = body weight (kg) x program calorie factor."""
    return int(weight_kg * PROGRAMS[code]["calorie_factor"])


def get_program_or_404(code):
    program = PROGRAMS.get(code.upper())
    if program is None:
        abort(404, description=f"Unknown program code '{code}'")
    return program


@bp.get("")
def list_programs():
    return jsonify(
        programs=[{"code": code, "name": p["name"]} for code, p in PROGRAMS.items()],
        site_metrics=SITE_METRICS,
    )


@bp.get("/<code>")
def program_detail(code):
    program = get_program_or_404(code)
    return jsonify(code=code.upper(), **program)


@bp.get("/<code>/calories")
def program_calories(code):
    program = get_program_or_404(code)
    try:
        weight = float(request.args.get("weight", ""))
    except ValueError:
        abort(400, description="Query parameter 'weight' must be a number")
    if weight <= 0:
        abort(400, description="Query parameter 'weight' must be greater than 0")
    return jsonify(
        program=program["name"],
        weight=weight,
        calorie_factor=program["calorie_factor"],
        calories=estimate_calories(weight, code.upper()),
    )
