"""Job status / progress."""
import app.routes


def test_unknown_job_returns_404(client):
    assert client.get("/jobs/does-not-exist").status_code == 404


def test_completed_job_status(client, payload):
    job_id = client.post("/jobs", json=payload()).json()["job_id"]
    job = client.get(f"/jobs/{job_id}").json()
    assert job["status"] == "completed"
    assert (job["total"], job["succeeded"], job["failed"], job["pending"]) == (2, 2, 0, 0)
    assert job["progress_percent"] == 100.0
    assert job["started_at"] and job["completed_at"]
    assert job["download_all_url"]


def test_job_is_pending_before_worker_runs(client, payload, monkeypatch):
    # Disable the background worker so we can observe the initial state.
    monkeypatch.setattr(app.routes, "process_job", lambda job_id: None)
    job_id = client.post("/jobs", json=payload()).json()["job_id"]
    job = client.get(f"/jobs/{job_id}").json()
    assert job["status"] == "pending"
    assert (job["succeeded"], job["failed"], job["pending"]) == (0, 0, 2)
    assert job["progress_percent"] == 0.0
    assert job["download_all_url"] is None
    assert all(c["status"] == "pending" and c["download_url"] is None for c in job["certificates"])


def test_status_filter_and_pagination(client, payload):
    recipients = [{"name": f"P{i}", "email": f"p{i}@example.com"} for i in range(5)]
    recipients.append({"name": "", "email": "x"})
    job_id = client.post("/jobs", json=payload(recipients)).json()["job_id"]

    failed = client.get(f"/jobs/{job_id}", params={"status": "failed"}).json()
    assert [c["index"] for c in failed["certificates"]] == [5]

    page = client.get(f"/jobs/{job_id}", params={"limit": 2, "offset": 2}).json()
    assert [c["index"] for c in page["certificates"]] == [2, 3]
    assert page["total"] == 6  # counts always describe the whole job

    assert client.get(f"/jobs/{job_id}", params={"status": "bogus"}).status_code == 422
