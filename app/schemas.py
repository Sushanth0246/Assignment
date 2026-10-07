"""Pydantic request/response models."""
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.config import settings


class JobCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    certificate_title: str = Field(min_length=1, max_length=120, examples=["Certificate of Completion"])
    course_name: str = Field(min_length=1, max_length=200, examples=["Introduction to Python"])
    issue_date: date = Field(examples=["2026-10-07"])
    # Items are deliberately typed as Any: each recipient is validated
    # individually (app/validation.py) so one bad entry doesn't reject the batch.
    recipients: list[Any] = Field(min_length=1)

    @field_validator("recipients")
    @classmethod
    def check_max_recipients(cls, v: list[Any]) -> list[Any]:
        if len(v) > settings.max_recipients:
            raise ValueError(f"at most {settings.max_recipients} recipients per job")
        return v


class JobCreated(BaseModel):
    job_id: str
    status: str
    total: int
    rejected_at_submission: int
    status_url: str


class CertificateOut(BaseModel):
    id: str
    index: int
    recipient_name: str | None
    recipient_email: str | None
    status: str
    error_message: str | None
    download_url: str | None


class JobOut(BaseModel):
    job_id: str
    status: str
    certificate_title: str
    course_name: str
    issue_date: date
    total: int
    succeeded: int
    failed: int
    pending: int
    progress_percent: float
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    download_all_url: str | None
    limit: int
    offset: int
    certificates: list[CertificateOut]
