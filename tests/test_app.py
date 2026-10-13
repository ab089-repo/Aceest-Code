"""Tests for application setup, the dashboard page and error handling."""
import sqlite3
from contextlib import closing

from app import create_app


# ---------- Factory and database ----------

def test_health_check(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "service": "aceest-fitness"}


def test_database_path_defaults_to_the_environment_variable(tmp_path, monkeypatch):
    database = tmp_path / "from_env.db"
    monkeypatch.setenv("ACEEST_DB", str(database))

    app = create_app()

    assert app.config["DATABASE"] == str(database)
    assert database.exists()


def test_test_config_overrides_the_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("ACEEST_DB", str(tmp_path / "from_env.db"))
    database = tmp_path / "override.db"

    app = create_app({"DATABASE": str(database)})

    assert app.config["DATABASE"] == str(database)
    assert not (tmp_path / "from_env.db").exists()


def test_create_app_builds_the_schema(app):
    with closing(sqlite3.connect(app.config["DATABASE"])) as conn:
        tables = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )}

    assert {"clients", "progress"} <= tables


def test_data_persists_across_app_instances(app, save_client):
    save_client()

    restarted = create_app({"TESTING": True, "DATABASE": app.config["DATABASE"]})
    response = restarted.test_client().get("/api/clients/Arun Kumar")

    assert response.status_code == 200
    assert response.get_json()["calories"] == 1595


# ---------- Dashboard ----------

def test_dashboard_lists_every_program(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    page = response.get_data(as_text=True)
    for name in ["Fat Loss (FL)", "Muscle Gain (MG)", "Beginner (BG)"]:
        assert name in page


def test_dashboard_shows_empty_state_without_clients(client):
    assert "No clients saved yet" in client.get("/").get_data(as_text=True)


def test_dashboard_shows_saved_clients(client, save_client):
    save_client()

    page = client.get("/").get_data(as_text=True)

    assert "Arun Kumar" in page
    assert "1595" in page
    assert "No clients saved yet" not in page


def test_dashboard_escapes_client_names(client, save_client):
    save_client(name="<script>alert(1)</script>")

    page = client.get("/").get_data(as_text=True)

    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page


# ---------- Error handling ----------

def test_unknown_route_returns_json_404(client):
    response = client.get("/api/does-not-exist")

    assert response.status_code == 404
    assert response.get_json() == {"error": "resource not found"}


def test_unsupported_method_returns_json_405(client):
    response = client.delete("/api/clients")

    assert response.status_code == 405
    assert response.get_json() == {"error": "method not allowed"}
