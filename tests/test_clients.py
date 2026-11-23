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
