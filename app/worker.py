"""Background job processor.

Runs after the HTTP response has been sent (see routes.create_job). Each
certificate is generated inside its own try/except and committed immediately,
so:
  * one bad certificate never stops the rest of the job, and
  * a client polling GET /jobs/{id} sees progress advance in real time.
"""
import logging
from pathlib import Path

from sqlalchemy import select

from app import database, generator
from app.config import settings
from app.models import Certificate, CertStatus, Job, JobStatus, utcnow

logger = logging.getLogger(__name__)


def _final_status(job: Job) -> str:
    if job.failed == 0:
        return JobStatus.COMPLETED
    if job.succeeded == 0:
        return JobStatus.FAILED
    return JobStatus.COMPLETED_WITH_ERRORS


def process_job(job_id: str) -> None:
    db = database.SessionLocal()
    try:
        job = db.get(Job, job_id)
        if job is None:
            logger.error("process_job: job %s not found", job_id)
            return

        job.status = JobStatus.PROCESSING
        job.started_at = utcnow()
        db.commit()

        pending = db.scalars(
            select(Certificate)
            .where(Certificate.job_id == job_id, Certificate.status == CertStatus.PENDING)
            .order_by(Certificate.index)
        ).all()

        job_dir = Path(settings.storage_dir) / job.id
        for cert in pending:
            path = job_dir / f"{cert.id}.pdf"
            try:
                generator.generate_certificate(
                    recipient_name=cert.recipient_name,
                    certificate_title=job.certificate_title,
                    course_name=job.course_name,
                    issue_date=job.issue_date,
                    certificate_id=cert.id,
                    output_path=path,
                )
                cert.status = CertStatus.SUCCESS
                cert.file_path = str(path)
                job.succeeded += 1
            except Exception as exc:  # noqa: BLE001 - isolate every failure
                logger.exception("Certificate %s (job %s) failed", cert.id, job_id)
                cert.status = CertStatus.FAILED
                cert.error_message = f"Generation failed: {exc}"[:500]
                job.failed += 1
                path.unlink(missing_ok=True)
            db.commit()  # persist progress after every certificate

        job.status = _final_status(job)
        job.completed_at = utcnow()
        db.commit()
    except Exception:  # noqa: BLE001 - something unexpected (e.g. DB down)
        logger.exception("Job %s crashed", job_id)
        db.rollback()
        job = db.get(Job, job_id)
        if job is not None:
            job.status = JobStatus.FAILED
            job.completed_at = utcnow()
            db.commit()
    finally:
        db.close()
