"""HTTP API."""
import io
import zipfile
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import services
from app.database import get_db
from app.models import Certificate, CertStatus, Job, JobStatus
from app.schemas import CertificateOut, JobCreate, JobCreated, JobOut
from app.worker import process_job

router = APIRouter()


def _get_job_or_404(db: Session, job_id: str) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/jobs", status_code=202, response_model=JobCreated)
def create_job(
    payload: JobCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
):
    """Accept a bulk request and return immediately; generation runs in the background."""
    job = services.create_job(db, payload)
    background_tasks.add_task(process_job, job.id)
    return JobCreated(
        job_id=job.id,
        status=job.status,
        total=job.total,
        rejected_at_submission=job.failed,
        status_url=str(request.url_for("get_job", job_id=job.id)),
    )


@router.get("/jobs/{job_id}", response_model=JobOut, name="get_job")
def get_job(
    job_id: str,
    request: Request,
    status: str | None = Query(None, pattern="^(pending|success|failed)$",
                               description="Filter certificates by status"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Job progress plus a (paginated, filterable) per-certificate breakdown."""
    job = _get_job_or_404(db, job_id)

    query = select(Certificate).where(Certificate.job_id == job_id)
    if status:
        query = query.where(Certificate.status == status)
    certs = db.scalars(query.order_by(Certificate.index).offset(offset).limit(limit)).all()

    processed = job.succeeded + job.failed
    items = [
        CertificateOut(
            id=c.id,
            index=c.index,
            recipient_name=c.recipient_name,
            recipient_email=c.recipient_email,
            status=c.status,
            error_message=c.error_message,
            download_url=(
                str(request.url_for("download_certificate", job_id=job.id, cert_id=c.id))
                if c.status == CertStatus.SUCCESS else None
            ),
        )
        for c in certs
    ]
    return JobOut(
        job_id=job.id,
        status=job.status,
        certificate_title=job.certificate_title,
        course_name=job.course_name,
        issue_date=job.issue_date,
        total=job.total,
        succeeded=job.succeeded,
        failed=job.failed,
        pending=job.total - processed,
        progress_percent=round(processed / job.total * 100, 1) if job.total else 100.0,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        download_all_url=(
            str(request.url_for("download_all", job_id=job.id))
            if job.status in JobStatus.FINISHED and job.succeeded > 0 else None
        ),
        limit=limit,
        offset=offset,
        certificates=items,
    )


@router.get("/jobs/{job_id}/certificates/{cert_id}", name="download_certificate")
def download_certificate(job_id: str, cert_id: str, db: Session = Depends(get_db)):
    """Download one generated certificate as a PDF."""
    _get_job_or_404(db, job_id)
    cert = db.get(Certificate, cert_id)
    if cert is None or cert.job_id != job_id:
        raise HTTPException(status_code=404, detail="Certificate not found")
    if cert.status != CertStatus.SUCCESS:
        raise HTTPException(
            status_code=409,
            detail=f"Certificate is not available (status: {cert.status})",
        )
    if not cert.file_path or not Path(cert.file_path).exists():
        raise HTTPException(status_code=404, detail="Certificate file is missing from storage")
    return FileResponse(
        cert.file_path,
        media_type="application/pdf",
        filename=services.certificate_filename(cert),
    )


@router.get("/jobs/{job_id}/download", name="download_all")
def download_all(job_id: str, db: Session = Depends(get_db)):
    """Download every successfully generated certificate in the job as one ZIP."""
    job = _get_job_or_404(db, job_id)
    if job.status not in JobStatus.FINISHED:
        raise HTTPException(
            status_code=409,
            detail=f"Job is still {job.status}; try again when it has finished",
        )
    certs = db.scalars(
        select(Certificate)
        .where(Certificate.job_id == job_id, Certificate.status == CertStatus.SUCCESS)
        .order_by(Certificate.index)
    ).all()
    if not certs:
        raise HTTPException(status_code=404, detail="No certificates were generated for this job")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for cert in certs:
            if cert.file_path and Path(cert.file_path).exists():
                zf.write(cert.file_path, arcname=services.certificate_filename(cert))
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="certificates_{job.id}.zip"'},
    )
