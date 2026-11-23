"""Tests for the weekly adherence progress chart (v2.2.1)."""


def test_chart_for_unknown_client_returns_404(client):
    assert client.get("/api/clients/Ghost/progress").status_code == 404


def test_chart_without_progress_is_empty(client, make_client):
    make_client("Arun")
    data = client.get("/api/clients/Arun/progress").get_json()
    assert data["weeks"] == []
    assert data["adherence"] == []
    assert data["average"] is None


def test_chart_lists_weeks_in_logged_order(client, make_client):
    make_client("Bala")
    for week, value in [("Week 01 - 2026", 60), ("Week 02 - 2026", 75), ("Week 03 - 2026", 90)]:
        client.post("/api/clients/Bala/progress", json={"adherence": value, "week": week})
    data = client.get("/api/clients/Bala/progress").get_json()
    assert data["title"] == "Weekly Adherence Progress - Bala"
    assert data["weeks"] == ["Week 01 - 2026", "Week 02 - 2026", "Week 03 - 2026"]
    assert data["adherence"] == [60, 75, 90]
    assert data["average"] == 75.0
    assert data["y_axis"] == {"label": "Adherence (%)", "min": 0, "max": 100}


def test_chart_includes_adherence_saved_with_profile(client, make_client):
    make_client("Chitra", adherence=55)
    assert client.get("/api/clients/Chitra/progress").get_json()["adherence"] == [55]


def test_charts_are_per_client(client, make_client):
    make_client("Dev", adherence=40)
    make_client("Esha", adherence=95)
    assert client.get("/api/clients/Dev/progress").get_json()["adherence"] == [40]
    assert client.get("/api/clients/Esha/progress").get_json()["adherence"] == [95]


def test_average_is_rounded(client, make_client):
    make_client("Faiz")
    for value in (70, 70, 71):
        client.post("/api/clients/Faiz/progress", json={"adherence": value})
    assert client.get("/api/clients/Faiz/progress").get_json()["average"] == 70.3
