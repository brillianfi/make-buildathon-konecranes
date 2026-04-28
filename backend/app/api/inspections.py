import json
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse
from pydantic import TypeAdapter
from pydantic import ValidationError as PydanticValidationError

from app.core.errors import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.domain.inspection import (
    AudioAsset,
    ImageAsset,
    ImageMeta,
    Inspection,
    InspectionStatus,
)
from app.services.pipeline import run_inspection
from app.services.template_loader import resolve_template
from app.storage.local import LocalStorage

log = get_logger(__name__)

router = APIRouter(prefix="/inspections", tags=["inspections"])

_REGISTRY: dict[UUID, Inspection] = {}

_ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
_ALLOWED_AUDIO_EXT = {".m4a", ".mp3", ".wav", ".ogg", ".flac", ".webm"}

_image_meta_list_adapter: TypeAdapter[list[ImageMeta]] = TypeAdapter(list[ImageMeta])


def _ext(filename: str | None) -> str:
    if not filename:
        return ""
    return filename[filename.rfind(".") :].lower() if "." in filename else ""


def _get_inspection(inspection_id: UUID) -> Inspection:
    inspection = _REGISTRY.get(inspection_id)
    if inspection is None:
        raise NotFoundError(f"Inspection {inspection_id} not found")
    return inspection


def _parse_metadata(raw: str) -> list[ImageMeta]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"metadata is not valid JSON: {exc}") from exc
    try:
        return _image_meta_list_adapter.validate_python(data)
    except PydanticValidationError as exc:
        raise ValidationError(f"metadata schema invalid: {exc}") from exc


@router.post("", response_model=Inspection, status_code=201)
def create_inspection(
    storage: Annotated[LocalStorage, Depends()],
    template_filename: Annotated[str, Form()],
    metadata: Annotated[str, Form(description="JSON array of {filename, captured_at, location?}")],
    images: Annotated[list[UploadFile], File()],
    audio: Annotated[UploadFile, File()],
    audio_started_at: Annotated[datetime | None, Form()] = None,
) -> Inspection:
    if not images:
        raise ValidationError("At least one image is required")

    resolve_template(template_filename)
    image_metas = _parse_metadata(metadata)
    meta_by_filename = {m.filename: m for m in image_metas}

    audio_ext = _ext(audio.filename)
    if audio_ext not in _ALLOWED_AUDIO_EXT:
        raise ValidationError(f"Unsupported audio type: {audio.filename}")

    inspection = Inspection(
        template_filename=template_filename,
        audio_started_at=audio_started_at,
    )

    for upload in images:
        ext = _ext(upload.filename)
        if ext not in _ALLOWED_IMAGE_EXT:
            raise ValidationError(f"Unsupported image type: {upload.filename}")
        filename = upload.filename or "image"
        meta = meta_by_filename.get(filename)
        if meta is None:
            raise ValidationError(f"Missing metadata for image: {filename}")
        path = storage.save_upload(inspection.id, "images", filename, upload.file)
        inspection.images.append(
            ImageAsset(
                filename=path.name,
                path=path,
                captured_at=meta.captured_at,
                location=meta.location,
            )
        )

    audio_path = storage.save_upload(inspection.id, "audio", audio.filename or "audio", audio.file)
    inspection.audio = AudioAsset(filename=audio_path.name, path=audio_path)

    _REGISTRY[inspection.id] = inspection
    log.info(
        "inspection.created",
        inspection_id=str(inspection.id),
        images=len(inspection.images),
    )
    return inspection


@router.post("/{inspection_id}/run", response_model=Inspection)
def run(
    inspection_id: UUID,
    storage: Annotated[LocalStorage, Depends()],
    background: BackgroundTasks,
    sync: bool = False,
) -> Inspection:
    inspection = _get_inspection(inspection_id)
    if inspection.status == InspectionStatus.RUNNING:
        return inspection

    if sync:
        run_inspection(inspection, storage)
    else:
        inspection.status = InspectionStatus.RUNNING
        background.add_task(run_inspection, inspection, storage)
    return inspection


@router.get("/{inspection_id}", response_model=Inspection)
def get_inspection(inspection_id: UUID) -> Inspection:
    return _get_inspection(inspection_id)


@router.get("/{inspection_id}/report")
def get_report(inspection_id: UUID) -> FileResponse:
    inspection = _get_inspection(inspection_id)
    if inspection.status != InspectionStatus.COMPLETED or inspection.report_path is None:
        raise ValidationError(
            f"Report not ready (status={inspection.status.value})",
        )
    return FileResponse(
        path=inspection.report_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"inspection-{inspection_id}.xlsx",
    )
