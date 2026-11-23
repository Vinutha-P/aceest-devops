"""ACEest Fitness & Gym - Flask web application package."""
import logging
import os
import secrets

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
        URL_PREFIX=os.environ.get("URL_PREFIX", ""),
        SECRET_KEY=os.environ.get("ACEEST_SECRET_KEY"),
        ADMIN_PASSWORD=os.environ.get("ACEEST_ADMIN_PASSWORD"),
        TOKEN_MAX_AGE=int(os.environ.get("ACEEST_TOKEN_MAX_AGE", str(8 * 3600))),
    )
    if test_config:
        app.config.update(test_config)

    if not app.testing:
        logging.basicConfig(
            level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s"
        )
    if not app.config["SECRET_KEY"]:
        # Tokens then only work on this instance; set ACEEST_SECRET_KEY in production
        app.logger.warning("ACEEST_SECRET_KEY not set - using a random per-process key")
        app.config["SECRET_KEY"] = secrets.token_hex(32)

    from . import ai_program, auth, clients, core, db, errors, programs, reports, tracking
    from .middleware import PrefixMiddleware

    db.init_app(app)
    with app.app_context():
        auth.bootstrap_admin(app)
    errors.register_error_handlers(app)
    for module in (core, programs, clients, tracking, auth, ai_program, reports):
        app.register_blueprint(module.bp)

    app.wsgi_app = PrefixMiddleware(app.wsgi_app, app.config["URL_PREFIX"])
    app.logger.info("ACEest v%s started (track=%s, prefix=%r)", __version__,
                    app.config["DEPLOYMENT_TRACK"], app.config["URL_PREFIX"])
    return app
