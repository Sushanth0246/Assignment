"""Creating a generation job."""


def test_create_job_returns_202_with_job_id(client, payload):
    res = client.post("/jobs", json=payload())
    assert res.status_code == 202
    body = res.json()
    assert body["job_id"]
    assert body["total"] == 2
    assert body["rejected_at_submission"] == 0
    assert body["status_url"].endswith(f"/jobs/{body['job_id']}")


def test_bulk_request_creates_one_certificate_per_recipient(client, payload):
    recipients = [{"name": f"Person {i}", "email": f"p{i}@example.com"} for i in range(25)]
    job_id = client.post("/jobs", json=payload(recipients)).json()["job_id"]

    job = client.get(f"/jobs/{job_id}", params={"limit": 1000}).json()
    assert job["total"] == 25
    assert len(job["certificates"]) == 25
    assert job["status"] == "completed"
    assert job["succeeded"] == 25


def test_certificates_keep_submission_order(client, payload):
    recipients = [{"name": n, "email": f"{n}@example.com"} for n in ["Cara", "Ben", "Alok"]]
    job_id = client.post("/jobs", json=payload(recipients)).json()["job_id"]
    certs = client.get(f"/jobs/{job_id}").json()["certificates"]
    assert [c["recipient_name"] for c in certs] == ["Cara", "Ben", "Alok"]
    assert [c["index"] for c in certs] == [0, 1, 2]
