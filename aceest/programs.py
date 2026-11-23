"""Training program catalogue (ported from Aceestver-1.0)."""
from flask import Blueprint, abort, jsonify

PROGRAMS = {
    "FL": {
        "name": "Fat Loss (FL)",
        "workout": [
            "Mon: 5x5 Back Squat + AMRAP",
            "Tue: EMOM 20min Assault Bike",
            "Wed: Bench Press + 21-15-9",
            "Thu: 10RFT Deadlifts/Box Jumps",
            "Fri: 30min Active Recovery",
        ],
        "diet": [
            "B: 3 Egg Whites + Oats Idli",
            "L: Grilled Chicken + Brown Rice",
            "D: Fish Curry + Millet Roti",
            "Target: 2,000 kcal",
        ],
        "color": "#e74c3c",
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
            "B: 4 Eggs + PB Oats",
            "L: Chicken Biryani (250g Chicken)",
            "D: Mutton Curry + Jeera Rice",
            "Target: 3,200 kcal",
        ],
        "color": "#2ecc71",
    },
    "BG": {
        "name": "Beginner (BG)",
        "workout": [
            "Circuit Training: Air Squats, Ring Rows, Push-ups",
            "Focus: Technique Mastery & Form (90% Threshold)",
        ],
        "diet": [
            "Balanced Tamil Meals: Idli-Sambar, Rice-Dal, Chapati",
            "Protein: 120g/day",
        ],
        "color": "#3498db",
    },
}

SITE_METRICS = {"capacity_users": 150, "area_sq_ft": 10000, "break_even_members": 250}

bp = Blueprint("programs", __name__, url_prefix="/api/programs")


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
