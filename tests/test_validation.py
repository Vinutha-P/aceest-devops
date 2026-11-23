"""Tests for input validation and JSON error handling (v2.1.2)."""
import pytest

from aceest import create_app
from aceest.validation import ValidationError, number, text


# ---------- unit tests for the helpers ----------

class TestText:
    def test_strips_whitespace(self):
        assert text({"name": "  Arun "}, "name") == "Arun"

    def test_missing_optional_field_is_empty(self):
        assert text({}, "notes") == ""

    def test_required_field_missing(self):
        with pytest.raises(ValidationError, match="'name' is required"):
            text({"name": "  "}, "name", required=True)

    def test_too_long(self):
        with pytest.raises(ValidationError, match="at most 5"):
            text({"name": "abcdef"}, "name", max_length=5)


class TestNumber:
    @pytest.mark.parametrize("raw,cast,expected", [
        ("42", int, 42), (42, int, 42), ("70.5", float, 70.5), (0, float, 0.0),
    ])
    def test_valid_values(self, raw, cast, expected):
        assert number({"x": raw}, "x", cast) == expected

    def test_default_when_missing(self):
        assert number({}, "x", int, default=7) == 7
        assert number({"x": ""}, "x", int, default=7) == 7

    def test_required(self):
        with pytest.raises(ValidationError, match="required"):
            number({}, "x", int, required=True)

    @pytest.mark.parametrize("raw", ["abc", [1], {"a": 1}, True, False])
    def test_rejects_non_numbers(self, raw):
        with pytest.raises(ValidationError, match="must be a number"):
            number({"x": raw}, "x", int)

    def test_minimum(self):
        with pytest.raises(ValidationError, match=">= 0"):
            number({"x": -1}, "x", int, minimum=0)

    def test_maximum(self):
        with pytest.raises(ValidationError, match="<= 100"):
            number({"x": 101}, "x", int, maximum=100)

    def test_boundaries_are_inclusive(self):
        assert number({"x": 0}, "x", int, minimum=0, maximum=100) == 0
        assert number({"x": 100}, "x", int, minimum=0, maximum=100) == 100


# ---------- API-level validation ----------

@pytest.mark.parametrize("field,value", [
    ("age", -1), ("age", 121),
    ("weight", -5), ("weight", 401),
    ("adherence", -1), ("adherence", 101),
])
def test_client_fields_out_of_range_are_rejected(client, field, value):
    response = client.post("/api/clients", json={"name": "Arun", "program": "FL", field: value})
    assert response.status_code == 400
    assert field in response.get_json()["error"]


def test_client_name_too_long_is_rejected(client):
    response = client.post("/api/clients", json={"name": "x" * 101, "program": "FL"})
    assert response.status_code == 400


def test_json_array_body_is_treated_as_empty(client):
    response = client.post("/api/clients", json=["Arun", "FL"])
    assert response.status_code == 400


@pytest.mark.parametrize("adherence", [-10, 150])
def test_progress_adherence_out_of_range(client, make_client, adherence):
    make_client("Bala")
    response = client.post("/api/clients/Bala/progress", json={"adherence": adherence})
    assert response.status_code == 400


def test_progress_boundary_values_accepted(client, make_client):
    make_client("Chitra")
    for value in (0, 100):
        assert client.post("/api/clients/Chitra/progress",
                           json={"adherence": value}).status_code == 201


# ---------- JSON error responses ----------

def test_unknown_route_returns_json_404(client):
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    assert response.is_json
    assert response.get_json()["error"] == "Not Found"


def test_wrong_method_returns_json_405(client):
    response = client.delete("/api/programs")
    assert response.status_code == 405
    assert response.get_json()["error"] == "Method Not Allowed"


def test_abort_400_has_json_message(client):
    body = client.get("/api/programs/FL/calories?weight=abc").get_json()
    assert body["error"] == "Bad Request"
    assert "weight" in body["message"]


def test_unhandled_exception_returns_json_500(tmp_path):
    app = create_app({"TESTING": False, "DATABASE": str(tmp_path / "t.db")})

    @app.get("/boom")
    def boom():
        raise RuntimeError("kaboom")

    response = app.test_client().get("/boom")
    assert response.status_code == 500
    body = response.get_json()
    assert body["error"] == "Internal Server Error"
    assert "kaboom" not in str(body)  # internal details are not leaked


class TestIsoDate:
    def test_valid_date_is_normalised(self):
        from aceest.validation import iso_date
        assert iso_date({"d": "2026-03-05"}, "d") == "2026-03-05"

    def test_default_used_when_missing(self):
        from aceest.validation import iso_date
        assert iso_date({}, "d", default="2026-01-01") == "2026-01-01"

    def test_required_without_default(self):
        from aceest.validation import iso_date
        with pytest.raises(ValidationError, match="required"):
            iso_date({}, "d")

    @pytest.mark.parametrize("raw", ["2026-13-01", "05/03/2026", "yesterday"])
    def test_invalid_dates(self, raw):
        from aceest.validation import iso_date
        with pytest.raises(ValidationError, match="YYYY-MM-DD"):
            iso_date({"d": raw}, "d")
