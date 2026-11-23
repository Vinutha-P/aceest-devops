"""Role-based user management (Aceestver-3.2.4 users table with roles) - Admin only."""
import sqlite3

from flask import Blueprint, jsonify, request

from .auth import ROLES, create_user, login_required
from .db import get_db
from .validation import ValidationError, json_body, text

bp = Blueprint("users", __name__, url_prefix="/api/users")

MIN_PASSWORD_LENGTH = 8


@bp.get("")
@login_required("Admin")
def list_users():
    rows = get_db().execute("SELECT username, role FROM users ORDER BY id").fetchall()
    return jsonify(users=[dict(r) for r in rows])


@bp.post("")
@login_required("Admin")
def add_user():
    data = json_body(request)
    username = text(data, "username", required=True, max_length=50)
    password = text(data, "password", required=True, max_length=200)
    role = text(data, "role") or "Trainer"
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValidationError(f"password must be at least {MIN_PASSWORD_LENGTH} characters")
    if role not in ROLES:
        raise ValidationError(f"role must be one of {', '.join(ROLES)}")
    db = get_db()
    try:
        create_user(db, username, password, role)
        db.commit()
    except sqlite3.IntegrityError:
        return jsonify(error=f"User '{username}' already exists"), 409
    return jsonify(message="User created", username=username, role=role), 201
