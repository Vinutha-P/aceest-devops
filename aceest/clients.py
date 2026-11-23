"""Client profile API (ported from Aceestver-1.1)."""
from flask import Blueprint, jsonify, request

from .programs import PROGRAMS, estimate_calories

bp = Blueprint("clients", __name__, url_prefix="/api/clients")


def _error(message, status=400):
    return jsonify(error=message), status


@bp.post("")
def save_client():
    """Validate a client profile and return it with the calorie estimate."""
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    program = str(data.get("program", "")).strip().upper()
    if not name or not program:
        return _error("Please fill client name and program.")
    if program not in PROGRAMS:
        return _error(f"Unknown program '{program}'")
    try:
        age = int(data.get("age", 0))
        weight = float(data.get("weight", 0))
        adherence = int(data.get("adherence", 0))
    except (TypeError, ValueError):
        return _error("age, weight and adherence must be numbers")

    client = {
        "name": name,
        "age": age,
        "weight": weight,
        "program": program,
        "adherence": adherence,
        "calories": estimate_calories(weight, program) if weight > 0 else None,
    }
    return jsonify(message=f"Client {name} saved successfully.", client=client), 201
