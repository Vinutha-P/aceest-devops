"""Tests for the PDF client report (v3.1.2)."""
import pytest

from aceest.reports import _latin1, _show


def _get_pdf(client, name, headers):
    return client.get(f"/api/clients/{name}/report.pdf", headers=headers)


def test_report_is_a_pdf_download(client, make_client, admin_headers):
    make_client("Arun", height=175, target_weight=68)
    response = _get_pdf(client, "Arun", admin_headers)
    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.data.startswith(b"%PDF")
    assert response.headers["Content-Disposition"] == "attachment; filename=Arun_report.pdf"


def test_report_with_full_activity(client, make_client, admin_headers):
    make_client("Bala", program="MG", height=180, weight=82)
    client.post("/api/clients/Bala/progress", json={"adherence": 80})
    for day in ("2026-01-01", "2026-01-02"):
        client.post("/api/clients/Bala/workouts",
                    json={"date": day, "workout_type": "Push", "duration_min": 60})
    response = _get_pdf(client, "Bala", admin_headers)
    assert response.status_code == 200
    assert len(response.data) > 1000


def test_report_handles_non_latin_names(client, make_client, admin_headers):
    make_client("Kavya கவியா")  # Tamil characters
    response = _get_pdf(client, "Kavya கவியா", admin_headers)
    assert response.status_code == 200
    assert "Kavya_" in response.headers["Content-Disposition"]


def test_report_requires_login(client, make_client):
    make_client("Chitra")
    assert _get_pdf(client, "Chitra", {}).status_code == 401


def test_report_unknown_client(client, admin_headers):
    assert _get_pdf(client, "Ghost", admin_headers).status_code == 404


@pytest.mark.parametrize("value,unit,expected", [
    (None, "", "-"), ("", " kg", "-"), (70, " kg", "70 kg"), (0, "", "0"),
])
def test_show_formats_missing_values(value, unit, expected):
    assert _show(value, unit) == expected


def test_latin1_replaces_unsupported_characters():
    assert _latin1("Café க") == "Café ?"
