"""Tests for the client profile API."""
import pytest


def test_save_client_returns_profile_with_calories(client):
    response = client.post("/api/clients", json={
        "name": "Arun", "age": 28, "weight": 75, "program": "FL", "adherence": 80,
    })
    assert response.status_code == 201
    body = response.get_json()
    assert body["message"] == "Client Arun saved successfully."
    assert body["client"]["calories"] == 75 * 22
    assert body["client"]["adherence"] == 80


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
    response = client.post("/api/clients", json={"name": "Esha", "program": "XX"})
    assert response.status_code == 400


def test_non_numeric_fields_are_rejected(client):
    response = client.post("/api/clients", json={"name": "Faiz", "program": "FL", "age": "old"})
    assert response.status_code == 400


def test_non_json_body_is_handled(client):
    response = client.post("/api/clients", data="not json", content_type="text/plain")
    assert response.status_code == 400


# ---------- v1.1.2: client list, CSV export, chart ----------

def _add(client, name, adherence=50, program="FL", notes=""):
    return client.post("/api/clients", json={
        "name": name, "age": 30, "weight": 70, "program": program,
        "adherence": adherence, "notes": notes,
    })


def test_list_clients_starts_empty(client):
    assert client.get("/api/clients").get_json() == {"count": 0, "clients": []}


def test_saved_clients_are_listed_in_order(client):
    _add(client, "Gita")
    _add(client, "Hari")
    data = client.get("/api/clients").get_json()
    assert data["count"] == 2
    assert [c["name"] for c in data["clients"]] == ["Gita", "Hari"]


def test_invalid_client_is_not_stored(client):
    client.post("/api/clients", json={"name": "NoProgram"})
    assert client.get("/api/clients").get_json()["count"] == 0


def test_export_csv_without_clients_returns_404(client):
    assert client.get("/api/clients/export.csv").status_code == 404


def test_export_csv_contains_header_and_rows(client):
    _add(client, "Indu", adherence=90, notes="knee injury")
    response = client.get("/api/clients/export.csv")
    assert response.status_code == 200
    assert response.mimetype == "text/csv"
    assert "attachment" in response.headers["Content-Disposition"]
    lines = response.get_data(as_text=True).strip().splitlines()
    assert lines[0] == "Name,Age,Weight,Program,Adherence,Notes"
    assert lines[1] == "Indu,30,70.0,FL,90,knee injury"


def test_chart_data_matches_clients(client):
    _add(client, "Jai", adherence=60)
    _add(client, "Kavya", adherence=85)
    data = client.get("/api/clients/chart").get_json()
    assert data["labels"] == ["Jai", "Kavya"]
    assert data["adherence"] == [60, 85]


def test_each_app_instance_has_its_own_store():
    from aceest import create_app

    first = create_app({"TESTING": True}).test_client()
    second = create_app({"TESTING": True}).test_client()
    _add(first, "Lakshmi")
    assert second.get("/api/clients").get_json()["count"] == 0
