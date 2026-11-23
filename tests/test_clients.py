"""Tests for the client profile API (v1.1 -> v2.0.1)."""
from datetime import datetime

import pytest

from aceest.clients import current_week_label


# ---------- create / validate (v1.1) ----------

def test_save_client_returns_profile_with_calories(client):
    response = client.post("/api/clients", json={
        "name": "Arun", "age": 28, "weight": 75, "program": "FL", "adherence": 80,
    })
    assert response.status_code == 201
    body = response.get_json()
    assert body["message"] == "Client Arun saved successfully."
    assert body["client"]["calories"] == 75 * 22
    assert body["client"]["latest_adherence"] == 80


def test_program_code_is_normalised(client):
    response = client.post("/api/clients", json={"name": "Bala", "program": "mg", "weight": 70})
    assert response.get_json()["client"]["program"] == "MG"


def test_calories_omitted_when_weight_missing(client):
    response = client.post("/api/clients", json={"name": "Chitra", "program": "BG"})
    assert response.status_code == 201
    assert response.get_json()["client"]["calories"] is None


@pytest.mark.parametrize("payload", [
    {},
    {"name": "", "program": "FL"},
    {"name": "Dev", "program": ""},
    {"name": "   ", "program": "FL"},
])
def test_name_and_program_are_required(client, payload):
    response = client.post("/api/clients", json=payload)
    assert response.status_code == 400
    assert "name and program" in response.get_json()["error"]


def test_unknown_program_is_rejected(client):
    assert client.post("/api/clients", json={"name": "Esha", "program": "XX"}).status_code == 400


@pytest.mark.parametrize("field", ["age", "weight", "adherence"])
def test_non_numeric_fields_are_rejected(client, field):
    payload = {"name": "Faiz", "program": "FL", field: "abc"}
    assert client.post("/api/clients", json=payload).status_code == 400


def test_non_json_body_is_handled(client):
    response = client.post("/api/clients", data="not json", content_type="text/plain")
    assert response.status_code == 400


# ---------- persistence (v2.0.1) ----------

def test_client_is_persisted_and_can_be_loaded(client, make_client):
    make_client("Gita", program="MG", age=35, weight=80, notes="morning batch")
    data = client.get("/api/clients/Gita").get_json()
    assert data["name"] == "Gita"
    assert data["age"] == 35
    assert data["calories"] == 80 * 35
    assert data["notes"] == "morning batch"
    assert "id" not in data


def test_unknown_client_returns_404(client):
    response = client.get("/api/clients/Nobody")
    assert response.status_code == 404
    assert response.get_json()["error"] == "Client not found"


def test_saving_same_name_updates_instead_of_duplicating(client, make_client):
    make_client("Hari", weight=70)
    response = client.post("/api/clients", json={"name": "Hari", "program": "MG", "weight": 90})
    assert response.status_code == 200
    data = client.get("/api/clients").get_json()
    assert data["count"] == 1
    assert data["clients"][0]["program"] == "MG"
    assert data["clients"][0]["calories"] == 90 * 35


def test_data_survives_app_restart(tmp_path):
    from aceest import create_app

    config = {"TESTING": True, "DATABASE": str(tmp_path / "shared.db")}
    create_app(config).test_client().post("/api/clients", json={"name": "Indu", "program": "BG"})
    restarted = create_app(config).test_client()
    assert restarted.get("/api/clients/Indu").status_code == 200


def test_separate_databases_are_isolated(tmp_path):
    from aceest import create_app

    first = create_app({"TESTING": True, "DATABASE": str(tmp_path / "a.db")}).test_client()
    second = create_app({"TESTING": True, "DATABASE": str(tmp_path / "b.db")}).test_client()
    first.post("/api/clients", json={"name": "Jai", "program": "FL"})
    assert second.get("/api/clients").get_json()["count"] == 0


# ---------- list, CSV and chart (v1.1.2) ----------

def test_list_clients_starts_empty(client):
    assert client.get("/api/clients").get_json() == {"count": 0, "clients": []}


def test_saved_clients_are_listed_in_order(client, make_client):
    make_client("Kavya")
    make_client("Lakshmi")
    data = client.get("/api/clients").get_json()
    assert [c["name"] for c in data["clients"]] == ["Kavya", "Lakshmi"]


def test_invalid_client_is_not_stored(client):
    client.post("/api/clients", json={"name": "NoProgram"})
    assert client.get("/api/clients").get_json()["count"] == 0


def test_export_csv_without_clients_returns_404(client):
    assert client.get("/api/clients/export.csv").status_code == 404


def test_export_csv_contains_header_and_rows(client, make_client):
    make_client("Mani", adherence=90, notes="knee injury")
    response = client.get("/api/clients/export.csv")
    assert response.status_code == 200
    assert response.mimetype == "text/csv"
    assert "attachment" in response.headers["Content-Disposition"]
    lines = response.get_data(as_text=True).strip().splitlines()
    assert lines[0] == "Name,Age,Weight,Program,Calories,Latest Adherence,Notes"
    assert lines[1] == "Mani,30,70.0,FL,1540,90,knee injury"


def test_chart_uses_latest_adherence_per_client(client, make_client):
    make_client("Nila", adherence=60)
    make_client("Om")
    client.post("/api/clients/Nila/progress", json={"adherence": 75})
    data = client.get("/api/clients/chart").get_json()
    assert data["labels"] == ["Nila", "Om"]
    assert data["adherence"] == [75, 0]


# ---------- weekly progress (v2.0.1) ----------

def test_week_label_format():
    assert current_week_label(datetime(2026, 1, 15)) == "Week 02 - 2026"


def test_log_progress_for_current_week(client, make_client):
    make_client("Priya")
    response = client.post("/api/clients/Priya/progress", json={"adherence": 85})
    assert response.status_code == 201
    body = response.get_json()
    assert body["week"] == current_week_label()
    assert body["adherence"] == 85
    assert client.get("/api/clients/Priya").get_json()["latest_adherence"] == 85


def test_log_progress_with_explicit_week(client, make_client):
    make_client("Ravi")
    body = client.post("/api/clients/Ravi/progress",
                       json={"adherence": 70, "week": "Week 01 - 2026"}).get_json()
    assert body["week"] == "Week 01 - 2026"


def test_progress_for_unknown_client_returns_404(client):
    assert client.post("/api/clients/Ghost/progress", json={"adherence": 50}).status_code == 404


@pytest.mark.parametrize("payload", [{}, {"adherence": "high"}, {"adherence": None}])
def test_progress_requires_numeric_adherence(client, make_client, payload):
    make_client("Sita")
    assert client.post("/api/clients/Sita/progress", json=payload).status_code == 400
