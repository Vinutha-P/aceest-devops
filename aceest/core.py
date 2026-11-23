"""Core routes and cross-cutting behaviour.

- dashboard page, liveness (/health), readiness (/ready) and /version
- response headers identifying the version / deployment track that served a request
  (used to observe blue-green, canary, A/B and shadow traffic splitting)
"""
import socket
import sqlite3
from datetime import date

from flask import Blueprint, current_app, jsonify, render_template

from .db import get_db
from .programs import PROGRAMS
from .version import __version__

bp = Blueprint("core", __name__)


def version_info():
    """Version details used by the UI and by deployment smoke tests."""
    return {
        "app": "ACEest Fitness & Gym",
        "version": __version__,
        "track": current_app.config["DEPLOYMENT_TRACK"],
        "pod": socket.gethostname(),
    }


@bp.after_app_request
def add_deployment_headers(response):
    response.headers["X-App-Version"] = __version__
    response.headers["X-Deployment-Track"] = current_app.config["DEPLOYMENT_TRACK"]
    response.headers["X-Served-By"] = socket.gethostname()
    return response


def dashboard_stats():
    db = get_db()
    today = date.today().isoformat()
    return {
        "clients": db.execute("SELECT COUNT(*) FROM clients").fetchone()[0],
        "active_members": db.execute(
            "SELECT COUNT(*) FROM clients WHERE membership_end >= ?", (today,)).fetchone()[0],
        "workouts": db.execute("SELECT COUNT(*) FROM workouts").fetchone()[0],
    }


@bp.get("/")
def index():
    return render_template("index.html", info=version_info(), programs=PROGRAMS,
                           stats=dashboard_stats())


@bp.get("/health")
def health():
    """Liveness probe - the process is up and serving requests."""
    return jsonify(status="ok")


@bp.get("/ready")
def ready():
    """Readiness probe - the app can reach its database and may receive traffic."""
    try:
        get_db().execute("SELECT 1").fetchone()
    except sqlite3.Error as exc:
        current_app.logger.warning("Readiness check failed: %s", exc)
        return jsonify(status="unavailable", reason="database"), 503
    return jsonify(status="ready", version=__version__)


@bp.get("/version")
def version():
    return jsonify(version_info())
