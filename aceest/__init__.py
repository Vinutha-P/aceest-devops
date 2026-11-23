"""ACEest Fitness & Gym - Flask web application package."""
import os

from flask import Flask

from .version import __version__

__all__ = ["create_app", "__version__"]


def create_app(test_config=None):
    """Application factory used by gunicorn, the tests and local development."""
    app = Flask(__name__)
    app.config.from_mapping(
        DEPLOYMENT_TRACK=os.environ.get("DEPLOYMENT_TRACK", "stable"),
        DATABASE=os.environ.get("ACEEST_DB")
        or os.path.join(app.instance_path, "aceest_fitness.db"),
    )
    if test_config:
        app.config.update(test_config)

    from . import clients, core, db, errors, programs

    db.init_app(app)
    errors.register_error_handlers(app)
    app.register_blueprint(core.bp)
    app.register_blueprint(programs.bp)
    app.register_blueprint(clients.bp)
    return app
