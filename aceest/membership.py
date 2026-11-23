"""Membership tracking (ported from Aceestver-3.2.4, check_membership)."""
from datetime import date, timedelta

from flask import Blueprint, jsonify, request

from .auth import login_required
from .clients import _client_row, _error
from .db import get_db
from .validation import json_body, number

bp = Blueprint("membership", __name__, url_prefix="/api/clients")

DAYS_PER_MONTH = 30


def membership_state(status, end, today=None):
    """Effective membership status: stored status, but 'Expired' once the end date passed."""
    today = today or date.today()
    if not end:
        return {"status": status or "None", "end": None, "days_remaining": None}
    end_date = date.fromisoformat(end)
    remaining = (end_date - today).days
    effective = "Expired" if remaining < 0 else (status or "Active")
    return {"status": effective, "end": end, "days_remaining": max(remaining, 0)}


def renewal_end(current_end, months, today=None):
    """New end date: extend from the current end if still valid, otherwise from today."""
    today = today or date.today()
    start = today
    if current_end and date.fromisoformat(current_end) > today:
        start = date.fromisoformat(current_end)
    return (start + timedelta(days=DAYS_PER_MONTH * months)).isoformat()


@bp.get("/<name>/membership")
@login_required()
def get_membership(name):
    client = _client_row(name)
    if client is None:
        return _error("Client not found", 404)
    return jsonify(client=name, **membership_state(client["membership_status"],
                                                   client["membership_end"]))


@bp.post("/<name>/membership")
@login_required("Admin")
def renew_membership(name):
    client = _client_row(name)
    if client is None:
        return _error("Client not found", 404)
    months = number(json_body(request), "months", int, required=True, minimum=1, maximum=24)
    end = renewal_end(client["membership_end"], months)
    db = get_db()
    db.execute("UPDATE clients SET membership_status = 'Active', membership_end = ? "
               "WHERE name = ?", (end, name))
    db.commit()
    return jsonify(message=f"Membership renewed for {months} month(s)", client=name,
                   **membership_state("Active", end))
