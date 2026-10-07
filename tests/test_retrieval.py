"""Retrieving generated certificates (single PDF and ZIP)."""
import io
import zipfile

import app.routes


def _run(client, payload, recipients=None):
    return client.post("/jobs", json=payload(recipients)).json()["job_id"]


def test_download_single_certificate(client, payload):
    job_id = _run(client, payload)
    cert = client.get(f"/jobs/{job_id}").json()["certificates"][0]

    res = client.get(cert["download_url"])
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.content.startswith(b"%PDF")
    assert "0000_asha_rao.pdf" in res.headers["content-disposition"]


def test_download_zip_contains_only_successful_certificates(client, payload):
    job_id = _run(client, payload, [
        {"name": "Asha Rao", "email": "asha@example.com"},
        {"name": "", "email": "bad"},
        {"name": "Rahul Verma", "email": "rahul@example.com"},
    ])
    res = client.get(f"/jobs/{job_id}/download")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/zip"

    with zipfile.ZipFile(io.BytesIO(res.content)) as zf:
        assert sorted(zf.namelist()) == ["0000_asha_rao.pdf", "0002_rahul_verma.pdf"]
        assert all(zf.read(n).startswith(b"%PDF") for n in zf.namelist())


def test_download_failed_certificate_returns_409(client, payload):
    job_id = _run(client, payload, [{"name": "", "email": "bad"}, {"name": "Ok", "email": "ok@example.com"}])
    failed = client.get(f"/jobs/{job_id}", params={"status": "failed"}).json()["certificates"][0]
    res = client.get(f"/jobs/{job_id}/certificates/{failed['id']}")
    assert res.status_code == 409


def test_unknown_job_or_certificate_returns_404(client, payload):
    job_id = _run(client, payload)
    assert client.get("/jobs/nope/download").status_code == 404
    assert client.get(f"/jobs/{job_id}/certificates/nope").status_code == 404


def test_certificate_cannot_be_fetched_through_another_job(client, payload):
    job_a = _run(client, payload)
    job_b = _run(client, payload)
    cert_a = client.get(f"/jobs/{job_a}").json()["certificates"][0]["id"]
    assert client.get(f"/jobs/{job_b}/certificates/{cert_a}").status_code == 404


def test_zip_not_available_until_job_finishes(client, payload, monkeypatch):
    monkeypatch.setattr(app.routes, "process_job", lambda job_id: None)
    job_id = _run(client, payload)
    assert client.get(f"/jobs/{job_id}/download").status_code == 409


def test_zip_404_when_nothing_was_generated(client, payload):
    job_id = _run(client, payload, [{"name": ""}])
    assert client.get(f"/jobs/{job_id}/download").status_code == 404
