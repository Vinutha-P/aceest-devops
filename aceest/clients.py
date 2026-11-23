"""Client profile API.

v1.1   - validate a client profile and estimate calories (Aceestver-1.1)
v1.1.2 - client list, CSV export and adherence chart data (Aceestver-1.1.2)
v2.0.1 - clients and weekly progress persisted in SQLite (Aceestver-2.0.1)
v2.1.2 - range validation and JSON error responses
v2.2.1 - weekly adherence progress chart data (Aceestver-2.2.1)
"""
import csv
import io
from datetime import datetime

from flask import Blueprint, Response, jsonify, request

from .db import get_db
from .programs import PROGRAMS, estimate_calories
from .validation import AGE_RANGE, PERCENT_RANGE, WEIGHT_RANGE, json_body, number, text

bp = Blueprint("clients", __name__, url_prefix="/api/clients")

CSV_HEADER = ["Name", "Age", "Weight", "Program", "Calories", "Latest Adherence", "Notes"]


def _error(message, status=400):
    return jsonify(error=message), status


def current_week_label(now=None):
    """Same label format as the desktop app, e.g. 'Week 07 - 2026'."""
    return (now or datetime.now()).strftime("Week %U - %Y")


def _client_row(name):
    return get_db().execute("SELECT * FROM clients WHERE name = ?", (name,)).fetchone()


def _latest_adherence(name):
    row = get_db().execute(
        "SELECT adherence FROM progress WHERE client_name = ? ORDER BY id DESC LIMIT 1", (name,)
    ).fetchone()
    return row["adherence"] if row else None


def _client_dict(row):
    client = dict(row)
    client.pop("id", None)
    client["latest_adherence"] = _latest_adherence(row["name"])
    return client


def _log_progress(name, adherence, week=None):
    db = get_db()
    week = week or current_week_label()
    db.execute(
        "INSERT INTO progress (client_name, week, adherence) VALUES (?, ?, ?)",
        (name, week, adherence),
    )
    db.commit()
    return week


@bp.post("")
def save_client():
    """Create or update a client (upsert by name) and return it with the calorie estimate."""
    data = json_body(request)
    name = text(data, "name")
    program = text(data, "program").upper()
    if not name or not program:
        return _error("Please fill client name and program.")
    if program not in PROGRAMS:
        return _error(f"Unknown program '{program}'")
    age = number(data, "age", int, default=0, **AGE_RANGE)
    weight = number(data, "weight", float, default=0.0, **WEIGHT_RANGE)
    adherence = number(data, "adherence", int, **PERCENT_RANGE)
    notes = text(data, "notes", max_length=500)

    calories = estimate_calories(weight, program) if weight > 0 else None
    existed = _client_row(name) is not None

    db = get_db()
    db.execute(
        """
        INSERT INTO clients (name, age, weight, program, calories, notes)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
            age = excluded.age, weight = excluded.weight, program = excluded.program,
            calories = excluded.calories, notes = excluded.notes
        """,
        (name, age, weight, program, calories, notes),
    )
    db.commit()
    if adherence is not None:
        _log_progress(name, adherence)

    saved = _client_dict(_client_row(name))
    status = 200 if existed else 201
    return jsonify(message=f"Client {name} saved successfully.", client=saved), status


@bp.get("")
def list_clients():
    rows = get_db().execute("SELECT * FROM clients ORDER BY id").fetchall()
    clients = [_client_dict(r) for r in rows]
    return jsonify(count=len(clients), clients=clients)


@bp.get("/export.csv")
def export_csv():
    rows = get_db().execute("SELECT * FROM clients ORDER BY id").fetchall()
    if not rows:
        return _error("No clients to export.", 404)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CSV_HEADER)
    for r in rows:
        writer.writerow([
            r["name"], r["age"], r["weight"], r["program"], r["calories"],
            _latest_adherence(r["name"]), r["notes"],
        ])
    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=aceest_clients.csv"},
    )


@bp.get("/chart")
def adherence_chart():
    """Data for the 'Client Progress' bar chart (latest adherence % per client)."""
    rows = get_db().execute("SELECT name FROM clients ORDER BY id").fetchall()
    names = [r["name"] for r in rows]
    return jsonify(
        title="Client Progress",
        labels=names,
        adherence=[_latest_adherence(n) or 0 for n in names],
    )


@bp.get("/<name>")
def get_client(name):
    row = _client_row(name)
    if row is None:
        return _error("Client not found", 404)
    return jsonify(_client_dict(row))


@bp.get("/<name>/progress")
def progress_chart(name):
    """Weekly adherence history (data for the 'Weekly Adherence Progress' line chart)."""
    if _client_row(name) is None:
        return _error("Client not found", 404)
    rows = get_db().execute(
        "SELECT week, adherence FROM progress WHERE client_name = ? ORDER BY id", (name,)
    ).fetchall()
    adherence = [r["adherence"] for r in rows]
    return jsonify(
        title=f"Weekly Adherence Progress - {name}",
        client=name,
        weeks=[r["week"] for r in rows],
        adherence=adherence,
        average=round(sum(adherence) / len(adherence), 1) if adherence else None,
        y_axis={"label": "Adherence (%)", "min": 0, "max": 100},
    )


@bp.post("/<name>/progress")
def save_progress(name):
    """Log weekly adherence for a client."""
    if _client_row(name) is None:
        return _error("Client not found", 404)
    data = json_body(request)
    adherence = number(data, "adherence", int, required=True, **PERCENT_RANGE)
    week = _log_progress(name, adherence, text(data, "week", max_length=30) or None)
    return jsonify(message="Weekly progress logged", client=name, week=week,
                   adherence=adherence), 201
