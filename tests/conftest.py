"""Shared fixtures: every test gets its own app backed by a throwaway database."""
import pytest

from app import create_app


@pytest.fixture
def app(tmp_path):
    return create_app({"TESTING": True, "DATABASE": str(tmp_path / "test.db")})


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def save_client(client):
    """Post a valid client, with any field overridden by keyword."""
    def _save(**overrides):
        payload = {"name": "Arun Kumar", "age": 28, "weight": 72.5, "program": "FL"}
        payload.update(overrides)
        return client.post("/api/clients", json=payload)
    return _save
