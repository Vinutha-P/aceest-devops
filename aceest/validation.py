"""Request validation helpers (v2.1.2).

Raising :class:`ValidationError` anywhere in a view produces a JSON 400 response
(see :mod:`aceest.errors`).
"""
from datetime import date

MAX_NAME_LENGTH = 100


class ValidationError(ValueError):
    """Invalid user input -> HTTP 400."""


def json_body(request):
    """Return the JSON object sent by the client, or an empty dict."""
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def text(data, field, required=False, max_length=MAX_NAME_LENGTH):
    value = data.get(field)
    value = "" if value is None else str(value).strip()
    if required and not value:
        raise ValidationError(f"'{field}' is required")
    if len(value) > max_length:
        raise ValidationError(f"'{field}' must be at most {max_length} characters")
    return value


def number(data, field, cast=float, minimum=None, maximum=None, required=False, default=None):
    """Parse ``data[field]`` as int/float and check its range."""
    raw = data.get(field)
    if raw is None or raw == "":
        if required:
            raise ValidationError(f"'{field}' is required")
        return default
    if isinstance(raw, bool):
        raise ValidationError(f"'{field}' must be a number")
    try:
        value = cast(raw)
    except (TypeError, ValueError):
        raise ValidationError(f"'{field}' must be a number") from None
    if minimum is not None and value < minimum:
        raise ValidationError(f"'{field}' must be >= {minimum}")
    if maximum is not None and value > maximum:
        raise ValidationError(f"'{field}' must be <= {maximum}")
    return value


# Ranges shared by the client, progress and metrics APIs
AGE_RANGE = {"minimum": 0, "maximum": 120}
WEIGHT_RANGE = {"minimum": 0, "maximum": 400}
HEIGHT_RANGE = {"minimum": 0, "maximum": 250}
DURATION_RANGE = {"minimum": 0, "maximum": 600}
COUNT_RANGE = {"minimum": 0, "maximum": 1000}
PERCENT_RANGE = {"minimum": 0, "maximum": 100}


def iso_date(data, field, default=None):
    """Validate a YYYY-MM-DD date string (returns ``default`` when missing)."""
    value = text(data, field, max_length=10)
    if not value:
        if default is None:
            raise ValidationError(f"'{field}' is required")
        return default
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise ValidationError(f"'{field}' must be a date in YYYY-MM-DD format") from None
