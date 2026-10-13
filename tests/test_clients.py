"""API tests for client profiles and weekly adherence tracking."""
import pytest

import app as app_module


# ---------- Saving and loading clients ----------

def test_create_client_returns_201_with_computed_calories(save_client):
    response = save_client()

    assert response.status_code == 201
    assert response.get_json() == {
        "id": 1,
        "name": "Arun Kumar",
        "age": 28,
        "weight": 72.5,
        "program": "FL",
        "program_name": "Fat Loss",
        "calories": 1595,
    }


def test_created_client_can_be_loaded_by_name(client, save_client):
    created = save_client().get_json()

    response = client.get("/api/clients/Arun Kumar")

    assert response.status_code == 200
    assert response.get_json() == created


def test_client_name_is_trimmed_before_saving(client, save_client):
    assert save_client(name="  Priya  ").get_json()["name"] == "Priya"
    assert client.get("/api/clients/Priya").status_code == 200


def test_client_can_be_saved_without_age(save_client):
    response = save_client(age=None)

    assert response.status_code == 201
    assert response.get_json()["age"] is None


def test_saving_an_existing_name_updates_the_client(client, save_client):
    original = save_client().get_json()

    response = save_client(weight=80, program="MG", age=29)

    assert response.status_code == 200
    updated = response.get_json()
    assert updated["id"] == original["id"]
    assert updated["program"] == "MG"
    assert updated["age"] == 29
    assert updated["calories"] == 2800
    assert len(client.get("/api/clients").get_json()["clients"]) == 1


def test_list_clients_is_empty_initially(client):
    response = client.get("/api/clients")

    assert response.status_code == 200
    assert response.get_json() == {"clients": []}


def test_list_clients_is_sorted_by_name(client, save_client):
    for name in ["Vikram", "Arun", "Meena"]:
        save_client(name=name)

    names = [c["name"] for c in client.get("/api/clients").get_json()["clients"]]

    assert names == ["Arun", "Meena", "Vikram"]


def test_get_unknown_client_returns_404(client):
    response = client.get("/api/clients/Nobody")

    assert response.status_code == 404
    assert "Nobody" in response.get_json()["error"]


@pytest.mark.parametrize("overrides, field", [
    ({"name": ""}, "name"),
    ({"name": None}, "name"),
    ({"program": "XX"}, "program"),
    ({"program": None}, "program"),
    ({"weight": 0}, "weight"),
    ({"weight": -10}, "weight"),
    ({"weight": "heavy"}, "weight"),
    ({"weight": None}, "weight"),
    ({"age": -1}, "age"),
    ({"age": "old"}, "age"),
])
def test_invalid_client_is_rejected_and_not_stored(client, save_client, overrides, field):
    response = save_client(**overrides)

    assert response.status_code == 400
    assert field in response.get_json()["error"]
    assert client.get("/api/clients").get_json()["clients"] == []


def test_client_body_must_be_json(client):
    response = client.post("/api/clients", data="name=Arun", content_type="text/plain")

    assert response.status_code == 400
    assert "JSON object" in response.get_json()["error"]


def test_client_body_must_be_a_json_object_not_a_list(client):
    response = client.post("/api/clients", json=["Arun", 28])

    assert response.status_code == 400


# ---------- Weekly adherence ----------

def test_log_progress_returns_201_with_the_current_week(client, save_client, monkeypatch):
    monkeypatch.setattr(app_module, "current_week_label", lambda: "Week 41 - 2026")
    save_client()

    response = client.post("/api/clients/Arun Kumar/progress", json={"adherence": 85})

    assert response.status_code == 201
    assert response.get_json() == {
        "client": "Arun Kumar",
        "week": "Week 41 - 2026",
        "adherence": 85,
    }


def test_progress_history_is_returned_in_logged_order(client, save_client):
    save_client()
    for adherence in [60, 75, 90]:
        client.post("/api/clients/Arun Kumar/progress", json={"adherence": adherence})

    response = client.get("/api/clients/Arun Kumar/progress")

    assert response.status_code == 200
    body = response.get_json()
    assert body["client"] == "Arun Kumar"
    assert [entry["adherence"] for entry in body["progress"]] == [60, 75, 90]
    assert all(entry["week"].startswith("Week ") for entry in body["progress"])


def test_progress_history_is_empty_for_a_new_client(client, save_client):
    save_client()

    assert client.get("/api/clients/Arun Kumar/progress").get_json()["progress"] == []


def test_progress_is_kept_separately_for_each_client(client, save_client):
    save_client(name="Arun")
    save_client(name="Meena")
    client.post("/api/clients/Arun/progress", json={"adherence": 40})
    client.post("/api/clients/Meena/progress", json={"adherence": 95})

    arun = client.get("/api/clients/Arun/progress").get_json()["progress"]
    meena = client.get("/api/clients/Meena/progress").get_json()["progress"]

    assert [entry["adherence"] for entry in arun] == [40]
    assert [entry["adherence"] for entry in meena] == [95]


def test_progress_survives_a_client_update(client, save_client):
    save_client()
    client.post("/api/clients/Arun Kumar/progress", json={"adherence": 70})

    save_client(weight=90)

    progress = client.get("/api/clients/Arun Kumar/progress").get_json()["progress"]
    assert [entry["adherence"] for entry in progress] == [70]


@pytest.mark.parametrize("method", ["get", "post"])
def test_progress_for_unknown_client_returns_404(client, method):
    response = getattr(client, method)("/api/clients/Nobody/progress", json={"adherence": 50})

    assert response.status_code == 404
    assert "Nobody" in response.get_json()["error"]


@pytest.mark.parametrize("payload", [
    {"adherence": -1},
    {"adherence": 101},
    {"adherence": "high"},
    {"adherence": 72.5},
    {},
])
def test_invalid_adherence_is_rejected_and_not_stored(client, save_client, payload):
    save_client()

    response = client.post("/api/clients/Arun Kumar/progress", json=payload)

    assert response.status_code == 400
    assert "adherence" in response.get_json()["error"]
    assert client.get("/api/clients/Arun Kumar/progress").get_json()["progress"] == []
