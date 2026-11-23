"""Tests for membership tracking and role-based users (v3.2.4)."""
from datetime import date, timedelta

import pytest

from aceest.membership import membership_state, renewal_end

TODAY = date(2026, 6, 1)


# ---------- pure functions ----------

def test_state_without_membership():
    assert membership_state(None, None, TODAY) == {
        "status": "None", "end": None, "days_remaining": None}


def test_state_active_with_days_remaining():
    assert membership_state("Active", "2026-06-11", TODAY) == {
        "status": "Active", "end": "2026-06-11", "days_remaining": 10}


def test_state_last_day_is_still_active():
    assert membership_state("Active", "2026-06-01", TODAY)["status"] == "Active"


def test_state_expired_after_end_date():
    state = membership_state("Active", "2026-05-31", TODAY)
    assert state["status"] == "Expired"
    assert state["days_remaining"] == 0


def test_renewal_from_today_when_no_membership():
    assert renewal_end(None, 1, TODAY) == "2026-07-01"


def test_renewal_from_today_when_expired():
    assert renewal_end("2026-01-01", 2, TODAY) == (TODAY + timedelta(days=60)).isoformat()


def test_renewal_extends_current_membership():
    assert renewal_end("2026-06-21", 1, TODAY) == "2026-07-21"


# ---------- membership API ----------

def test_new_client_has_no_membership(client, make_client, admin_headers):
    make_client("Arun")
    body = client.get("/api/clients/Arun/membership", headers=admin_headers).get_json()
    assert body["status"] == "None"


def test_admin_renews_membership(client, make_client, admin_headers):
    make_client("Bala")
    response = client.post("/api/clients/Bala/membership", json={"months": 3},
                           headers=admin_headers)
    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "Active"
    assert body["end"] == (date.today() + timedelta(days=90)).isoformat()
    assert body["days_remaining"] == 90

    again = client.post("/api/clients/Bala/membership", json={"months": 1},
                        headers=admin_headers).get_json()
    assert again["days_remaining"] == 120  # extended, not reset


def test_membership_shows_in_summary_and_dashboard(client, make_client, admin_headers):
    make_client("Chitra")
    client.post("/api/clients/Chitra/membership", json={"months": 1}, headers=admin_headers)
    summary = client.get("/api/clients/Chitra/summary").get_json()
    assert summary["membership"]["status"] == "Active"
    html = client.get("/").get_data(as_text=True)
    assert "Active memberships" in html


def test_report_includes_membership(client, make_client, admin_headers):
    make_client("Dev")
    client.post("/api/clients/Dev/membership", json={"months": 6}, headers=admin_headers)
    assert client.get("/api/clients/Dev/report.pdf", headers=admin_headers).status_code == 200


@pytest.mark.parametrize("payload", [{}, {"months": 0}, {"months": 25}, {"months": "many"}])
def test_invalid_renewal_period(client, make_client, admin_headers, payload):
    make_client("Esha")
    assert client.post("/api/clients/Esha/membership", json=payload,
                       headers=admin_headers).status_code == 400


def test_membership_requires_login(client, make_client):
    make_client("Faiz")
    assert client.get("/api/clients/Faiz/membership").status_code == 401
    assert client.post("/api/clients/Faiz/membership", json={"months": 1}).status_code == 401


def test_membership_unknown_client(client, admin_headers):
    assert client.get("/api/clients/Ghost/membership", headers=admin_headers).status_code == 404
    assert client.post("/api/clients/Ghost/membership", json={"months": 1},
                       headers=admin_headers).status_code == 404


# ---------- users & roles ----------

@pytest.fixture
def trainer_headers(client, admin_headers, login):
    client.post("/api/users", headers=admin_headers,
                json={"username": "trainer1", "password": "trainer-pass-1", "role": "Trainer"})
    return login("trainer1", "trainer-pass-1")


def test_admin_creates_trainer_who_can_log_in(client, trainer_headers):
    assert client.get("/api/auth/me", headers=trainer_headers).get_json() == {
        "username": "trainer1", "role": "Trainer"}


def test_default_role_is_trainer(client, admin_headers):
    body = client.post("/api/users", headers=admin_headers,
                       json={"username": "coach", "password": "coach-pass-1"}).get_json()
    assert body["role"] == "Trainer"


def test_admin_lists_users(client, admin_headers, trainer_headers):
    users = client.get("/api/users", headers=admin_headers).get_json()["users"]
    assert users == [{"username": "admin", "role": "Admin"},
                     {"username": "trainer1", "role": "Trainer"}]


def test_trainer_cannot_manage_users(client, trainer_headers):
    assert client.get("/api/users", headers=trainer_headers).status_code == 403
    response = client.post("/api/users", headers=trainer_headers,
                           json={"username": "x", "password": "password1"})
    assert response.status_code == 403
    assert "permission" in response.get_json()["error"]


def test_trainer_can_view_but_not_renew_membership(client, make_client, trainer_headers):
    make_client("Gita")
    assert client.get("/api/clients/Gita/membership", headers=trainer_headers).status_code == 200
    assert client.post("/api/clients/Gita/membership", json={"months": 1},
                       headers=trainer_headers).status_code == 403


def test_trainer_can_use_ai_program(client, make_client, trainer_headers):
    make_client("Hari")
    assert client.post("/api/clients/Hari/ai-program", json={"experience": "beginner"},
                       headers=trainer_headers).status_code == 200


def test_duplicate_username_returns_409(client, admin_headers):
    payload = {"username": "dup", "password": "password-123"}
    assert client.post("/api/users", json=payload, headers=admin_headers).status_code == 201
    assert client.post("/api/users", json=payload, headers=admin_headers).status_code == 409


@pytest.mark.parametrize("payload,message", [
    ({"password": "password-123"}, "username"),
    ({"username": "u1"}, "password"),
    ({"username": "u1", "password": "short"}, "at least 8"),
    ({"username": "u1", "password": "password-123", "role": "Owner"}, "role must be"),
])
def test_invalid_new_users(client, admin_headers, payload, message):
    response = client.post("/api/users", json=payload, headers=admin_headers)
    assert response.status_code == 400
    assert message in response.get_json()["error"]


def test_users_endpoints_require_login(client):
    assert client.get("/api/users").status_code == 401
