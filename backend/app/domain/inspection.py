from datetime import datetime
from enum import StrEnum
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.domain.transcript import Transcript


class InspectionStatus(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ImageMeta(BaseModel):
    """Metadata supplied by the frontend for a single image."""

    filename: str
    captured_at: datetime
    location: str | None = None


class ImageAsset(BaseModel):
    filename: str
    path: Path
    captured_at: datetime
    location: str | None = None


class AudioAsset(BaseModel):
    filename: str
    path: Path


class Finding(BaseModel):
    image: str
    component: str | None = None
    condition: str | None = None
    severity: str | None = None
    observation: str
    recommendation: str | None = None


class Inspection(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    template_filename: str | None = None
    status: InspectionStatus = InspectionStatus.CREATED
    images: list[ImageAsset] = Field(default_factory=list)
    audio: AudioAsset | None = None
    audio_started_at: datetime | None = None
    audio_language: str | None = None
    transcript: Transcript | None = None
    findings: list[Finding] = Field(default_factory=list)
    report_path: Path | None = None
    error: str | None = None
