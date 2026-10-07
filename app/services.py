"""Business logic kept out of the route handlers."""
import re
from typing import Any

from sqlalchemy.orm import Session

from app.models import Certificate, CertStatus, Job, JobStatus
from app.schemas import JobCreate
from app.validation import validate_recipient


def _safe_str(raw: Any, key: str) -> str | None:
    """Best-effort copy of a raw field so failed rows still show what was sent."""
    if isinstance(raw, dict) and isinstance(raw.get(key), str):
        return raw[key][:255]
    return None


def create_job(db: Session, payload: JobCreate) -> Job:
    """Persist a job plus one Certificate row per recipient.

    Valid recipients start as `pending`; invalid ones are stored immediately as
    `failed` with the validation error, and counted in job.failed.
    """
    job = Job(
        status=JobStatus.PENDING,
        certificate_title=payload.certificate_title,
        course_name=payload.course_name,
        issue_date=payload.issue_date,
        total=len(payload.recipients),
        succeeded=0,
        failed=0,
    )
    for index, raw in enumerate(payload.recipients):
        clean, error = validate_recipient(raw)
        if clean:
            cert = Certificate(
                index=index,
                recipient_name=clean["name"],
                recipient_email=clean["email"],
                status=CertStatus.PENDING,
            )
        else:
            cert = Certificate(
                index=index,
                recipient_name=_safe_str(raw, "name"),
                recipient_email=_safe_str(raw, "email"),
                status=CertStatus.FAILED,
                error_message=error,
            )
            job.failed += 1
        job.certificates.append(cert)

    db.add(job)
    db.commit()
    return job


def certificate_filename(cert: Certificate) -> str:
    """Human-friendly download name, e.g. 0003_asha_rao.pdf"""
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", cert.recipient_name or "").strip("_").lower()[:40]
    return f"{cert.index:04d}_{slug or 'certificate'}.pdf"
