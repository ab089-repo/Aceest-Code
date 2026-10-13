"""API tests for the program catalogue and the calorie estimate."""
import pytest


def test_list_programs_returns_all_three_in_order(client):
    response = client.get("/api/programs")

    assert response.status_code == 200
    programs = response.get_json()["programs"]
    assert [p["code"] for p in programs] == ["FL", "MG", "BG"]
    assert [p["name"] for p in programs] == ["Fat Loss", "Muscle Gain", "Beginner"]


def test_listed_programs_include_workout_and_diet_plans(client):
    for program in client.get("/api/programs").get_json()["programs"]:
        assert program["calorie_factor"] > 0
        assert program["workout"]
        assert program["diet"]


def test_get_program_by_code(client):
    response = client.get("/api/programs/MG")

    assert response.status_code == 200
    program = response.get_json()
    assert program["code"] == "MG"
    assert program["name"] == "Muscle Gain"
    assert program["calorie_factor"] == 35
    assert "Mon: Squat 5x5" in program["workout"]


def test_get_program_code_is_case_insensitive(client):
    assert client.get("/api/programs/fl").get_json()["code"] == "FL"


def test_get_unknown_program_returns_404(client):
    response = client.get("/api/programs/XX")

    assert response.status_code == 404
    assert "not found" in response.get_json()["error"]


@pytest.mark.parametrize("query, expected", [
    ("weight=70&program=MG", 2450),
    ("weight=70&program=fl", 1540),
    ("weight=72.5&program=FL", 1595),
])
def test_calorie_estimate(client, query, expected):
    response = client.get(f"/api/calories?{query}")

    assert response.status_code == 200
    assert response.get_json()["calories"] == expected


def test_calorie_estimate_echoes_the_inputs(client):
    body = client.get("/api/calories?weight=70&program=mg").get_json()
    assert body == {"program": "MG", "weight": 70.0, "calories": 2450}


@pytest.mark.parametrize("query", [
    "program=MG",
    "weight=abc&program=MG",
    "weight=0&program=MG",
    "weight=-5&program=MG",
    "weight=nan&program=MG",
    "weight=inf&program=MG",
])
def test_calorie_estimate_rejects_bad_weight(client, query):
    response = client.get(f"/api/calories?{query}")

    assert response.status_code == 400
    assert "weight" in response.get_json()["error"]


@pytest.mark.parametrize("query", ["weight=70", "weight=70&program=XX"])
def test_calorie_estimate_rejects_bad_program(client, query):
    response = client.get(f"/api/calories?{query}")

    assert response.status_code == 400
    assert "program" in response.get_json()["error"]
