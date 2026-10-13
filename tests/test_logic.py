"""Unit tests for the domain logic and request validation in app.py."""
import re
from datetime import datetime

import pytest

from app import (
    PROGRAMS,
    ValidationError,
    calculate_calories,
    current_week_label,
    parse_program,
    program_details,
    validate_adherence,
    validate_client,
)

VALID_CLIENT = {"name": "Arun Kumar", "age": 28, "weight": 72.5, "program": "FL"}


def client_payload(**overrides):
    return {**VALID_CLIENT, **overrides}


# ---------- Programs ----------

def test_programs_cover_the_three_aceest_plans():
    assert list(PROGRAMS) == ["FL", "MG", "BG"]


@pytest.mark.parametrize("code", list(PROGRAMS))
def test_every_program_has_a_complete_plan(code):
    program = PROGRAMS[code]
    assert program["name"]
    assert program["calorie_factor"] > 0
    assert program["workout"] and all(isinstance(line, str) for line in program["workout"])
    assert program["diet"] and all(isinstance(line, str) for line in program["diet"])


def test_program_details_adds_the_code_to_the_plan():
    details = program_details("MG")
    assert details["code"] == "MG"
    assert details["name"] == "Muscle Gain"
    assert details["workout"] == PROGRAMS["MG"]["workout"]


# ---------- Calories ----------

@pytest.mark.parametrize("weight, program, expected", [
    (70, "FL", 1540),
    (70, "MG", 2450),
    (70, "BG", 1820),
    (72.5, "FL", 1595),
])
def test_calories_are_weight_times_program_factor(weight, program, expected):
    assert calculate_calories(weight, program) == expected


def test_calories_are_truncated_to_a_whole_number():
    # 60.9 kg x 26 = 1583.4
    assert calculate_calories(60.9, "BG") == 1583


def test_calories_for_unknown_program_raise_key_error():
    with pytest.raises(KeyError):
        calculate_calories(70, "XX")


# ---------- Week label ----------

@pytest.mark.parametrize("day, expected", [
    (datetime(2026, 10, 13), "Week 41 - 2026"),
    (datetime(2026, 1, 1), "Week 00 - 2026"),
    (datetime(2025, 12, 31), "Week 52 - 2025"),
])
def test_week_label_for_a_given_day(day, expected):
    assert current_week_label(day) == expected


def test_week_label_defaults_to_today():
    assert re.fullmatch(r"Week \d{2} - \d{4}", current_week_label())


# ---------- Program parsing ----------

@pytest.mark.parametrize("value, expected", [
    ("FL", "FL"),
    ("mg", "MG"),
    ("  bg  ", "BG"),
])
def test_parse_program_normalises_case_and_whitespace(value, expected):
    assert parse_program(value) == expected


@pytest.mark.parametrize("value", ["XX", "", "Fat Loss", None, 5])
def test_parse_program_rejects_unknown_values(value):
    with pytest.raises(ValidationError, match="program must be one of"):
        parse_program(value)


# ---------- Client validation ----------

def test_valid_client_is_returned_unchanged():
    assert validate_client(VALID_CLIENT) == VALID_CLIENT


def test_client_name_is_trimmed_and_program_upper_cased():
    client = validate_client(client_payload(name="  Arun Kumar  ", program="fl"))
    assert client["name"] == "Arun Kumar"
    assert client["program"] == "FL"


def test_client_integer_weight_is_stored_as_float():
    weight = validate_client(client_payload(weight=70))["weight"]
    assert weight == 70.0
    assert isinstance(weight, float)


def test_client_age_is_optional():
    payload = client_payload()
    del payload["age"]
    assert validate_client(payload)["age"] is None


@pytest.mark.parametrize("body", [None, [], "Arun", 42])
def test_client_body_must_be_a_json_object(body):
    with pytest.raises(ValidationError, match="JSON object"):
        validate_client(body)


@pytest.mark.parametrize("name", [None, "", "   ", 123])
def test_client_name_is_required(name):
    with pytest.raises(ValidationError, match="name is required"):
        validate_client(client_payload(name=name))


@pytest.mark.parametrize("program", [None, "XX", 7])
def test_client_program_must_be_known(program):
    with pytest.raises(ValidationError, match="program must be one of"):
        validate_client(client_payload(program=program))


@pytest.mark.parametrize("weight", [None, 0, -5, "70", True, float("nan"), float("inf")])
def test_client_weight_must_be_a_positive_number(weight):
    with pytest.raises(ValidationError, match="weight must be a positive number"):
        validate_client(client_payload(weight=weight))


@pytest.mark.parametrize("age", [0, -3, "30", 27.5, True])
def test_client_age_must_be_a_positive_integer(age):
    with pytest.raises(ValidationError, match="age must be a positive integer"):
        validate_client(client_payload(age=age))


# ---------- Adherence validation ----------

@pytest.mark.parametrize("adherence", [0, 55, 100])
def test_adherence_within_range_is_accepted(adherence):
    assert validate_adherence({"adherence": adherence}) == adherence


@pytest.mark.parametrize("adherence", [-1, 101, "50", 50.5, True, None])
def test_adherence_must_be_an_integer_from_0_to_100(adherence):
    with pytest.raises(ValidationError, match="adherence must be an integer"):
        validate_adherence({"adherence": adherence})


@pytest.mark.parametrize("body", [None, [], "85"])
def test_adherence_body_must_be_a_json_object(body):
    with pytest.raises(ValidationError, match="JSON object"):
        validate_adherence(body)
