# Bulk Certificate Generator

A backend API that accepts **one request containing many recipients**, generates a
PDF certificate for each from a single predefined template, tracks progress, and
lets the client retrieve the results (individually or as a ZIP).

**Stack:** Python 3.10+, FastAPI, SQLAlchemy 2 + SQLite, ReportLab, pytest.

## Project structure

```
bulk-certificate-generator/
├── app/
│   ├── main.py          # FastAPI app, startup (creates tables)
│   ├── routes.py        # HTTP endpoints
│   ├── schemas.py       # Pydantic request/response models
│   ├── models.py        # SQLAlchemy models: Job, Certificate
│   ├── services.py      # create_job(): validate + persist recipients
│   ├── validation.py    # per-recipient validation rules
│   ├── generator.py     # the certificate template (ReportLab PDF)
│   ├── worker.py        # background processing of a job
│   ├── database.py      # engine / session
│   └── config.py        # settings (env-overridable)
├── tests/               # pytest suite (jobs, validation, generator, status, failures, retrieval)
├── sample_request.json
├── requirements.txt / requirements-dev.txt
└── pytest.ini
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
```

## Run

```bash
uvicorn app.main:app --reload
```

- API: http://127.0.0.1:8000
- Interactive docs (Swagger): http://127.0.0.1:8000/docs

The SQLite DB (`certificates.db`) and generated PDFs (`storage/certificates/<job_id>/`)
are created automatically. Optional env vars: `DATABASE_URL`, `CERT_STORAGE_DIR`,
`MAX_RECIPIENTS` (default 1000).

## Run tests

```bash
pytest
```

Tests use a temporary database and directory, so they never touch real data.

## API usage

### 1. Submit a generation request

```bash
curl -X POST http://127.0.0.1:8000/jobs \
  -H "Content-Type: application/json" \
  -d @sample_request.json
```

Request body:

| Field | Rules |
|---|---|
| `certificate_title` | required, 1–120 chars |
| `course_name` | required, 1–200 chars |
| `issue_date` | required, `YYYY-MM-DD` |
| `recipients` | required, 1 to `MAX_RECIPIENTS` items, each `{ "name": str (≤100), "email": valid email }` |

Response `202 Accepted` (returned immediately; generation continues in the background):

```json
{
  "job_id": "3f1c...",
  "status": "pending",
  "total": 3,
  "rejected_at_submission": 1,
  "status_url": "http://127.0.0.1:8000/jobs/3f1c..."
}
```

### 2. Check progress

```bash
curl http://127.0.0.1:8000/jobs/<job_id>
```

Returns `status` (`pending` → `processing` → `completed` | `completed_with_errors` | `failed`),
counts (`total`, `succeeded`, `failed`, `pending`, `progress_percent`) and a per-certificate
list with `index` (position in your request), `status`, `error_message` and `download_url`.

Query params: `?status=failed|success|pending`, `?limit=` (default 100, max 1000), `?offset=`.
Example, list only failures: `GET /jobs/<job_id>?status=failed`.

### 3. Retrieve certificates

```bash
# one certificate (use download_url from the status response)
curl -OJ http://127.0.0.1:8000/jobs/<job_id>/certificates/<cert_id>

# every successful certificate in the job, as a ZIP (only once the job has finished)
curl -OJ http://127.0.0.1:8000/jobs/<job_id>/download
```

### Endpoint summary

| Method | Path | Description |
|---|---|---|
| POST | `/jobs` | Create a bulk job (202) |
| GET | `/jobs/{job_id}` | Status, progress, per-certificate results |
| GET | `/jobs/{job_id}/certificates/{cert_id}` | Download one PDF (409 if that certificate failed/not ready) |
| GET | `/jobs/{job_id}/download` | ZIP of all successful PDFs (409 until job finished) |
| GET | `/health` | Liveness check |

## Design decisions

**Background processing (not synchronous).** Rendering up to 1000 PDFs inside one HTTP
request would be slow, risk client/proxy timeouts, and tie up a worker. `POST /jobs`
therefore only validates and stores the job, returns `202` with a `job_id`, and the
work runs after the response via FastAPI `BackgroundTasks`. Clients poll `GET /jobs/{id}`.
Each certificate is committed as soon as it finishes, so progress is visible live.

**Why `BackgroundTasks` and its limits.** It needs no extra infrastructure, which keeps the
project easy to run. The trade-off: tasks live in the server process, so a restart mid-job
leaves that job stuck in `processing`, and there is no retry or horizontal scaling.
For production I would swap `process_job` to a queue (Celery/RQ + Redis) — the worker
function is already isolated and takes only a `job_id`, so the change is confined to
`routes.create_job`.

**Two-level validation.**
- *Request level* (empty list, too many recipients, missing title/course, bad date) → `422`, nothing stored.
- *Recipient level* (missing name, bad email, wrong type) → the job is still accepted; the bad
  recipient is stored as a `failed` certificate with a clear `error_message` and its original
  `index`, while valid recipients proceed. This satisfies "one bad record must not block the others".

**Failure isolation.** Each certificate is generated in its own `try/except`. A failure marks only
that certificate `failed` (error stored, partial file deleted) and the loop continues. Final
job status: `completed` (0 failed), `completed_with_errors` (some of each), `failed` (none succeeded).

**Safe file writes.** The PDF is written to a `.tmp` file and atomically renamed, so a crash never
leaves a half-written certificate that looks valid.

**Data model.** `jobs` (status, counts, timestamps) 1—N `certificates` (index, recipient, status,
file path, error). Counters are stored on the job so status checks are O(1); the per-certificate
list is paginated because jobs can be large.

**Storage.** PDFs are stored on local disk under `storage/certificates/<job_id>/<cert_id>.pdf`,
the database stores the path. For multi-server deployments this would move to object storage (S3).

**ZIP download** is built in memory, which is fine at ≤1000 small PDFs; larger jobs should stream
from a temp file or pre-built archive.

## Known limitations / possible extensions

- Built-in PDF fonts only support Latin-1 characters; names in other scripts need a registered TTF font.
- No authentication or rate limiting.
- No duplicate-email detection within a job; no retry endpoint for failed certificates.
- Stuck-job recovery after a crash (re-queue jobs left in `pending`/`processing` on startup).
