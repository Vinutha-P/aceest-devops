"""Consistent JSON error responses (v2.1.2)."""
from flask import jsonify
from werkzeug.exceptions import HTTPException, InternalServerError

from .validation import ValidationError


def register_error_handlers(app):
    @app.errorhandler(ValidationError)
    def handle_validation_error(exc):
        return jsonify(error=str(exc)), 400

    @app.errorhandler(HTTPException)
    def handle_http_error(exc):
        return jsonify(error=exc.name, message=exc.description), exc.code

    @app.errorhandler(InternalServerError)
    def handle_internal_error(exc):
        app.logger.exception("Unhandled error: %s", getattr(exc, "original_exception", exc))
        return jsonify(error="Internal Server Error",
                       message="Something went wrong, please try again later."), 500
