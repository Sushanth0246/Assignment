"""Input validation: request-level (422) and recipient-level (recorded as failed)."""
import pytest

from app.config import settings
from app.validation import validate_recipient


# ---- request level -> 422 -------------------------------------------------
def test_empty_recipient_list_is_rejected(client, payload):
    assert client.post("/jobs", json=payload([])).status_code == 422


def test_missing_course_name_is_rejected(client, payload):
    body = payload()
    del body["course_name"]
    assert client.post("/jobs", json=body).status_code == 422


def test_blank_title_is_rejected(client, payload):
    assert client.post("/jobs", json=payload(certificate_title="   ")).status_code == 422


def test_invalid_issue_date_is_rejected(client, payload):
    assert client.post("/jobs", json=payload(issue_date="not-a-date")).status_code == 422


def test_too_many_recipients_is_rejected(client, payload, monkeypatch):
    monkeypatch.setattr(settings, "max_recipients", 2)
    recipients = [{"name": f"P{i}", "email": f"p{i}@example.com"} for i in range(3)]
    res = client.post("/jobs", json=payload(recipients))
    assert res.status_code == 422


# ---- recipient level -> accepted, but marked failed -------------------------
@pytest.mark.parametrize(
    "raw",
    [
        {"email": "a@example.com"},                      # missing name
        {"name": "", "email": "a@example.com"},          # empty name
        {"name": "   ", "email": "a@example.com"},       # blank name
        {"name": "A" * 101, "email": "a@example.com"},   # name too long
        {"name": "Asha"},                                # missing email
        {"name": "Asha", "email": "not-an-email"},       # bad email
        {"name": 123, "email": "a@example.com"},         # wrong type
        "just a string",                                 # not an object
        None,
    ],
)
def test_invalid_recipients_are_rejected_by_validator(raw):
    clean, error = validate_recipient(raw)
    assert clean is None
    assert error


def test_valid_recipient_is_cleaned():
    clean, error = validate_recipient({"name": "  Asha Rao ", "email": " asha@example.com "})
    assert error is None
    assert clean == {"name": "Asha Rao", "email": "asha@example.com"}


def test_invalid_recipient_does_not_reject_the_batch(client, payload):
    recipients = [
        {"name": "Good One", "email": "good@example.com"},
        {"name": "", "email": "bad-email"},
        {"name": "Good Two", "email": "good2@example.com"},
    ]
    res = client.post("/jobs", json=payload(recipients))
    assert res.status_code == 202
    assert res.json()["rejected_at_submission"] == 1

    job = client.get(f"/jobs/{res.json()['job_id']}").json()
    assert job["succeeded"] == 2
    assert job["failed"] == 1
    bad = job["certificates"][1]
    assert bad["status"] == "failed"
    assert bad["index"] == 1
    assert "name is required" in bad["error_message"]
    assert "email" in bad["error_message"]
