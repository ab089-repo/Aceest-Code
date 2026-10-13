"""ACEest Fitness & Gym - Flask web application.

Web port of the ACEest desktop baseline: training programs, calorie
estimates, client profiles and weekly adherence tracking.
"""
import math
import os
import sqlite3
from contextlib import closing
from datetime import datetime

from flask import Flask, current_app, g, jsonify, render_template, request

PROGRAMS = {
    "FL": {
        "name": "Fat Loss",
        "calorie_factor": 22,
        "workout": [
            "Mon: Back Squat 5x5 + Core",
            "Tue: EMOM 20min Assault Bike",
            "Wed: Bench Press + 21-15-9",
            "Thu: Deadlift + Box Jumps",
            "Fri: Zone 2 Cardio 30min",
        ],
        "diet": [
            "Breakfast: Egg Whites + Oats",
            "Lunch: Grilled Chicken + Brown Rice",
            "Dinner: Fish Curry + Millet Roti",
            "Target: ~2000 kcal",
        ],
    },
    "MG": {
        "name": "Muscle Gain",
        "calorie_factor": 35,
        "workout": [
            "Mon: Squat 5x5",
            "Tue: Bench 5x5",
            "Wed: Deadlift 4x6",
            "Thu: Front Squat 4x8",
            "Fri: Incline Press 4x10",
            "Sat: Barbell Rows 4x10",
        ],
        "diet": [
            "Breakfast: Eggs + Peanut Butter Oats",
            "Lunch: Chicken Biryani",
            "Dinner: Mutton Curry + Rice",
            "Target: ~3200 kcal",
        ],
    },
    "BG": {
        "name": "Beginner",
        "calorie_factor": 26,
        "workout": [
            "Full Body Circuit:",
            "- Air Squats",
            "- Ring Rows",
            "- Push-ups",
            "Focus: Technique & Consistency",
        ],
        "diet": [
            "Balanced Tamil Meals",
            "Idli / Dosa / Rice + Dal",
            "Protein Target: 120g/day",
        ],
    },
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    age INTEGER,
    weight REAL NOT NULL,
    program TEXT NOT NULL,
    calories INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_name TEXT NOT NULL,
    week TEXT NOT NULL,
    adherence INTEGER NOT NULL
);
"""


class ValidationError(ValueError):
    """Raised when request data does not meet the API contract."""


# ---------- Domain logic ----------

def calculate_calories(weight, program_code):
    """Estimate daily calories as body weight (kg) times the program factor."""
    return int(weight * PROGRAMS[program_code]["calorie_factor"])


def current_week_label(today=None):
    """Return the label progress entries are filed under, e.g. 'Week 41 - 2026'."""
    return (today or datetime.now()).strftime("Week %U - %Y")


def program_details(code):
    return {"code": code, **PROGRAMS[code]}


def _is_positive_number(value):
    # bool is a subclass of int, and nan/inf parse as floats: reject both
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return math.isfinite(value) and value > 0


def parse_program(value):
    if not isinstance(value, str) or value.strip().upper() not in PROGRAMS:
        raise ValidationError(f"program must be one of: {', '.join(PROGRAMS)}")
    return value.strip().upper()


def validate_client(data):
    """Validate a client payload and return it in normalised form."""
    if not isinstance(data, dict):
        raise ValidationError("request body must be a JSON object")

    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValidationError("name is required")

    program = parse_program(data.get("program"))

    weight = data.get("weight")
    if not _is_positive_number(weight):
        raise ValidationError("weight must be a positive number (kg)")

    age = data.get("age")
    if age is not None and (not isinstance(age, int) or isinstance(age, bool) or age <= 0):
        raise ValidationError("age must be a positive integer")

    return {"name": name.strip(), "age": age, "weight": float(weight), "program": program}


def validate_adherence(data):
    """Validate a progress payload and return the adherence percentage."""
    if not isinstance(data, dict):
        raise ValidationError("request body must be a JSON object")

    adherence = data.get("adherence")
    if not isinstance(adherence, int) or isinstance(adherence, bool) or not 0 <= adherence <= 100:
        raise ValidationError("adherence must be an integer between 0 and 100")
    return adherence


# ---------- Database ----------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(database):
    with closing(sqlite3.connect(database)) as conn:
        conn.executescript(SCHEMA)
        conn.commit()


def client_to_dict(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "age": row["age"],
        "weight": row["weight"],
        "program": row["program"],
        "program_name": PROGRAMS[row["program"]]["name"],
        "calories": row["calories"],
    }


def find_client(name):
    return get_db().execute("SELECT * FROM clients WHERE name = ?", (name,)).fetchone()


# ---------- Application factory ----------

def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(DATABASE=os.environ.get("ACEEST_DB", "aceest_fitness.db"))
    if test_config:
        app.config.update(test_config)

    init_db(app.config["DATABASE"])
    app.teardown_appcontext(close_db)

    @app.errorhandler(ValidationError)
    def handle_validation_error(error):
        return jsonify(error=str(error)), 400

    @app.errorhandler(404)
    def handle_not_found(_error):
        return jsonify(error="resource not found"), 404

    @app.errorhandler(405)
    def handle_method_not_allowed(_error):
        return jsonify(error="method not allowed"), 405

    @app.get("/")
    def index():
        rows = get_db().execute("SELECT * FROM clients ORDER BY name").fetchall()
        return render_template(
            "index.html",
            programs=[program_details(code) for code in PROGRAMS],
            clients=[client_to_dict(row) for row in rows],
        )

    @app.get("/health")
    def health():
        return jsonify(status="ok", service="aceest-fitness")

    @app.get("/api/programs")
    def list_programs():
        return jsonify(programs=[program_details(code) for code in PROGRAMS])

    @app.get("/api/programs/<code>")
    def get_program(code):
        code = code.upper()
        if code not in PROGRAMS:
            return jsonify(error=f"program '{code}' not found"), 404
        return jsonify(program_details(code))

    @app.get("/api/calories")
    def estimate_calories():
        program = parse_program(request.args.get("program"))
        weight = request.args.get("weight", type=float)
        if not _is_positive_number(weight):
            raise ValidationError("weight must be a positive number (kg)")
        return jsonify(
            program=program,
            weight=weight,
            calories=calculate_calories(weight, program),
        )

    @app.get("/api/clients")
    def list_clients():
        rows = get_db().execute("SELECT * FROM clients ORDER BY name").fetchall()
        return jsonify(clients=[client_to_dict(row) for row in rows])

    @app.post("/api/clients")
    def save_client():
        client = validate_client(request.get_json(silent=True))
        calories = calculate_calories(client["weight"], client["program"])
        created = find_client(client["name"]) is None

        db = get_db()
        db.execute(
            """
            INSERT INTO clients (name, age, weight, program, calories)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                age = excluded.age,
                weight = excluded.weight,
                program = excluded.program,
                calories = excluded.calories
            """,
            (client["name"], client["age"], client["weight"], client["program"], calories),
        )
        db.commit()
        return jsonify(client_to_dict(find_client(client["name"]))), 201 if created else 200

    @app.get("/api/clients/<name>")
    def get_client(name):
        row = find_client(name)
        if row is None:
            return jsonify(error=f"client '{name}' not found"), 404
        return jsonify(client_to_dict(row))

    @app.get("/api/clients/<name>/progress")
    def get_progress(name):
        if find_client(name) is None:
            return jsonify(error=f"client '{name}' not found"), 404
        rows = get_db().execute(
            "SELECT week, adherence FROM progress WHERE client_name = ? ORDER BY id",
            (name,),
        ).fetchall()
        return jsonify(client=name, progress=[dict(row) for row in rows])

    @app.post("/api/clients/<name>/progress")
    def save_progress(name):
        if find_client(name) is None:
            return jsonify(error=f"client '{name}' not found"), 404
        adherence = validate_adherence(request.get_json(silent=True))
        week = current_week_label()

        db = get_db()
        db.execute(
            "INSERT INTO progress (client_name, week, adherence) VALUES (?, ?, ?)",
            (name, week, adherence),
        )
        db.commit()
        return jsonify(client=name, week=week, adherence=adherence), 201

    return app


if __name__ == "__main__":
    create_app().run(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "5000")),
    )
