"""Client profile API.

v1.1   - validate a client profile and estimate calories (Aceestver-1.1)
v1.1.2 - keep a list of clients, CSV export and adherence chart data (Aceestver-1.1.2)
"""
import csv
import io

from flask import Blueprint, Response, current_app, jsonify, request

from .programs import PROGRAMS, estimate_calories

bp = Blueprint("clients", __name__, url_prefix="/api/clients")

CSV_HEADER = ["Name", "Age", "Weight", "Program", "Adherence", "Notes"]


def _error(message, status=400):
    return jsonify(error=message), status


def _store():
    """In-memory client store (one per application instance)."""
    return current_app.extensions.setdefault("aceest_clients", [])


@bp.post("")
def save_client():
    """Validate a client profile, store it and return it with the calorie estimate."""
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
        "notes": str(data.get("notes", "")).strip(),
        "calories": estimate_calories(weight, program) if weight > 0 else None,
    }
    _store().append(client)
    return jsonify(message=f"Client {name} saved successfully.", client=client), 201


@bp.get("")
def list_clients():
    clients = _store()
    return jsonify(count=len(clients), clients=clients)


@bp.get("/export.csv")
def export_csv():
    clients = _store()
    if not clients:
        return _error("No clients to export.", 404)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CSV_HEADER)
    for c in clients:
        writer.writerow(
            [c["name"], c["age"], c["weight"], c["program"], c["adherence"], c["notes"]]
        )
    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=aceest_clients.csv"},
    )


@bp.get("/chart")
def adherence_chart():
    """Data for the 'Client Progress' bar chart (adherence % per client)."""
    clients = _store()
    return jsonify(
        title="Client Progress",
        labels=[c["name"] for c in clients],
        adherence=[c["adherence"] for c in clients],
    )
