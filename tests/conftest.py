import pytest
from fastapi.testclient import TestClient

from app import database
from app.config import settings
from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    """App wired to a throwaway SQLite DB and a temp certificate directory.

    TestClient runs FastAPI background tasks before returning the response, so
    by the time client.post() returns, the job has already been processed.
    """
    monkeypatch.setattr(settings, "storage_dir", tmp_path / "certs")
    database.configure(f"sqlite:///{tmp_path / 'test.db'}")
    with TestClient(app) as c:
        yield c
    database.engine.dispose()


def make_payload(recipients=None, **overrides):
    payload = {
        "certificate_title": "Certificate of Completion",
        "course_name": "Intro to Python",
        "issue_date": "2026-10-07",
        "recipients": recipients
        if recipients is not None
        else [
            {"name": "Asha Rao", "email": "asha@example.com"},
            {"name": "Rahul Verma", "email": "rahul@example.com"},
        ],
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def payload():
    return make_payload
