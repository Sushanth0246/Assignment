"""One failing certificate must not stop the rest of the job."""
from app import generator


def _make_flaky(real, bad_name):
    def flaky(*, recipient_name, **kwargs):
        if recipient_name == bad_name:
            raise RuntimeError("simulated rendering error")
        return real(recipient_name=recipient_name, **kwargs)
    return flaky


def test_single_generation_failure_does_not_block_others(client, payload, monkeypatch):
    monkeypatch.setattr(generator, "generate_certificate",
                        _make_flaky(generator.generate_certificate, "Boom"))
    recipients = [
        {"name": "Alice", "email": "alice@example.com"},
        {"name": "Boom", "email": "boom@example.com"},
        {"name": "Carol", "email": "carol@example.com"},
    ]
    job_id = client.post("/jobs", json=payload(recipients)).json()["job_id"]
    job = client.get(f"/jobs/{job_id}").json()

    assert job["status"] == "completed_with_errors"
    assert (job["succeeded"], job["failed"]) == (2, 1)

    by_name = {c["recipient_name"]: c for c in job["certificates"]}
    assert by_name["Alice"]["status"] == "success"
    assert by_name["Carol"]["status"] == "success"
    assert by_name["Boom"]["status"] == "failed"
    assert "simulated rendering error" in by_name["Boom"]["error_message"]
    assert by_name["Boom"]["download_url"] is None


def test_failed_certificate_leaves_no_file(client, payload, monkeypatch, tmp_path):
    monkeypatch.setattr(generator, "generate_certificate",
                        _make_flaky(generator.generate_certificate, "Boom"))
    job_id = client.post("/jobs", json=payload([
        {"name": "Boom", "email": "boom@example.com"},
        {"name": "Fine", "email": "fine@example.com"},
    ])).json()["job_id"]
    files = list((tmp_path / "certs" / job_id).glob("*"))
    assert len(files) == 1 and files[0].suffix == ".pdf"


def test_job_fails_when_every_recipient_is_invalid(client, payload):
    job_id = client.post("/jobs", json=payload([{"name": ""}, "oops"])).json()["job_id"]
    job = client.get(f"/jobs/{job_id}").json()
    assert job["status"] == "failed"
    assert (job["succeeded"], job["failed"]) == (0, 2)
    assert job["download_all_url"] is None


def test_validation_failures_and_generation_failures_are_combined(client, payload, monkeypatch):
    monkeypatch.setattr(generator, "generate_certificate",
                        _make_flaky(generator.generate_certificate, "Boom"))
    job_id = client.post("/jobs", json=payload([
        {"name": "Ok", "email": "ok@example.com"},
        {"name": "Boom", "email": "boom@example.com"},
        {"name": "", "email": "nope"},
    ])).json()["job_id"]
    job = client.get(f"/jobs/{job_id}").json()
    assert job["status"] == "completed_with_errors"
    assert (job["succeeded"], job["failed"], job["pending"]) == (1, 2, 0)
