"""Authentication (ported from the login screen of Aceestver-3.1.2).

Improvements over the desktop app:
- passwords are stored as salted hashes (werkzeug), never in plain text
- no hard-coded admin/admin: the bootstrap admin password comes from the
  ACEEST_ADMIN_PASSWORD environment variable (a Kubernetes Secret); if it is not
  set a random one is generated and written to the log once
- stateless signed tokens (itsdangerous), so any replica can verify a request
"""
import functools
import secrets

from flask import Blueprint, current_app, g, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db
from .validation import json_body, text

bp = Blueprint("auth", __name__, url_prefix="/api/auth")

ROLES = ("Admin", "Trainer")
TOKEN_SALT = "aceest-auth"

USERS_TABLE = """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'Trainer'
    )
"""


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=TOKEN_SALT)


def issue_token(username, role):
    return _serializer().dumps({"u": username, "r": role})


def create_user(db, username, password, role="Trainer"):
    method = current_app.config.get("PASSWORD_HASH_METHOD", "scrypt")
    db.execute(
        "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
        (username, generate_password_hash(password, method=method), role),
    )


def bootstrap_admin(app):
    """Create the users table and the first admin account if no users exist."""
    db = get_db()
    db.execute(USERS_TABLE)
    if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        password = app.config.get("ADMIN_PASSWORD")
        if not password:
            password = secrets.token_urlsafe(12)
            app.logger.warning(
                "ACEEST_ADMIN_PASSWORD not set - generated admin password: %s", password)
        create_user(db, "admin", password, "Admin")
    db.commit()


def login_required(*roles):
    """Require a valid 'Authorization: Bearer <token>' header (optionally one of ``roles``)."""

    def decorator(view):
        @functools.wraps(view)
        def wrapped(*args, **kwargs):
            header = request.headers.get("Authorization", "")
            if not header.startswith("Bearer "):
                return jsonify(error="Authentication required"), 401
            try:
                data = _serializer().loads(
                    header[len("Bearer "):], max_age=current_app.config["TOKEN_MAX_AGE"])
            except SignatureExpired:
                return jsonify(error="Token expired, please log in again"), 401
            except BadSignature:
                return jsonify(error="Invalid token"), 401
            g.user = {"username": data["u"], "role": data["r"]}
            if roles and g.user["role"] not in roles:
                return jsonify(error="You do not have permission for this action"), 403
            return view(*args, **kwargs)

        return wrapped

    return decorator


@bp.post("/login")
def login():
    data = json_body(request)
    username = text(data, "username")
    password = text(data, "password", max_length=200)
    row = get_db().execute(
        "SELECT username, password_hash, role FROM users WHERE username = ?", (username,)
    ).fetchone()
    if row is None or not check_password_hash(row["password_hash"], password):
        return jsonify(error="Invalid credentials"), 401
    return jsonify(
        token=issue_token(row["username"], row["role"]),
        username=row["username"],
        role=row["role"],
        expires_in=current_app.config["TOKEN_MAX_AGE"],
    )


@bp.get("/me")
@login_required()
def me():
    return jsonify(g.user)
