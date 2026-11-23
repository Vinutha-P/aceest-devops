"""Core routes: dashboard page, health check and version information."""
import socket

from flask import Blueprint, current_app, jsonify, render_template

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


@bp.get("/")
def index():
    return render_template("index.html", info=version_info(), programs=PROGRAMS)


@bp.get("/health")
def health():
    """Liveness probe - the process is up and serving requests."""
    return jsonify(status="ok")


@bp.get("/version")
def version():
    return jsonify(version_info())
