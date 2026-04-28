"""Glue between the GUI and the FastAPI backend.

- collect_from_folders(): walk image folders and return records in the
  {filename, filepath, captured_at} shape the backend's ImageMeta accepts.
- list_templates / create_inspection / run_inspection / download_report:
  HTTP wrappers around the four backend endpoints we use.
"""

from __future__ import annotations

import contextlib
import json
import mimetypes
import os
import re
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import IO, Any, cast

import requests
from PIL import ExifTags, Image

DEFAULT_BASE_URL = "http://localhost:8000"
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")

_TIMEOUT = (10, 600)  # connect, read — pipeline can take minutes
_DJI_RE = re.compile(r"DJI_(\d{14})_")

# Multipart entry shape: (field_name, (filename, fileobj, content_type)).
_MultipartEntry = tuple[str, tuple[str, IO[bytes], str]]
JsonDict = dict[str, Any]


# ---------------- Image timestamps ----------------

def _exif_datetime(path: Path) -> datetime | None:
    try:
        with Image.open(path) as img:
            exif = img._getexif()  # type: ignore[attr-defined]
        if not exif:
            return None
        for tag_id, value in exif.items():
            tag = ExifTags.TAGS.get(tag_id)
            if tag in ("DateTimeOriginal", "DateTime") and isinstance(value, str):
                return datetime.strptime(value, "%Y:%m:%d %H:%M:%S")
    except Exception:
        return None
    return None


def _filename_datetime(name: str) -> datetime | None:
    m = _DJI_RE.search(name)
    return datetime.strptime(m.group(1), "%Y%m%d%H%M%S") if m else None


def collect_from_folders(
    folders: Iterable[str | os.PathLike[str]],
) -> tuple[list[JsonDict], int]:
    """Return (records_sorted_by_capture_time, skipped_count).

    Records: {filename, filepath, captured_at (ISO-8601 string)}.
    Images without any recoverable timestamp are skipped and counted.
    """
    seen: set[Path] = set()
    candidates: list[Path] = []
    for folder in folders:
        p = Path(folder)
        if not p.is_dir():
            continue
        for entry in p.iterdir():
            if entry.is_file() and entry.suffix.lower() in IMAGE_EXTENSIONS:
                rp = entry.resolve()
                if rp not in seen:
                    seen.add(rp)
                    candidates.append(entry)

    records: list[tuple[datetime, JsonDict]] = []
    skipped = 0
    for path in candidates:
        ts = _exif_datetime(path) or _filename_datetime(path.name)
        if ts is None:
            skipped += 1
            continue
        records.append(
            (
                ts,
                {
                    "filename": path.name,
                    "filepath": str(path),
                    "captured_at": ts.strftime("%Y-%m-%dT%H:%M:%S"),
                },
            )
        )
    records.sort(key=lambda r: r[0])
    return [rec for _, rec in records], skipped


# ---------------- Backend HTTP ----------------

def _check(resp: requests.Response) -> requests.Response:
    if not resp.ok:
        try:
            detail: Any = resp.json()
        except ValueError:
            detail = resp.text
        raise RuntimeError(f"{resp.status_code} {resp.reason}: {detail}")
    return resp


def _mime(path: Path, default: str) -> str:
    return mimetypes.guess_type(path.name)[0] or default


def list_templates(base_url: str = DEFAULT_BASE_URL) -> list[JsonDict]:
    resp = _check(requests.get(f"{base_url}/templates", timeout=_TIMEOUT))
    return cast(list[JsonDict], resp.json())


def create_inspection(
    audio_path: str | Path,
    image_paths: Iterable[str | Path],
    metadata: list[JsonDict],
    template_filename: str,
    base_url: str = DEFAULT_BASE_URL,
) -> JsonDict:
    audio = Path(audio_path)
    images = [Path(p) for p in image_paths]

    handles: list[IO[bytes]] = []
    files: list[_MultipartEntry] = []

    audio_fh = audio.open("rb")
    handles.append(audio_fh)
    files.append(
        ("audio", (audio.name, audio_fh, _mime(audio, "application/octet-stream")))
    )
    for img in images:
        fh = img.open("rb")
        handles.append(fh)
        files.append(("images", (img.name, fh, _mime(img, "image/jpeg"))))

    try:
        resp = _check(
            requests.post(
                f"{base_url}/inspections",
                data={
                    "template_filename": template_filename,
                    "metadata": json.dumps(metadata),
                },
                files=files,
                timeout=_TIMEOUT,
            )
        )
        return cast(JsonDict, resp.json())
    finally:
        for handle in handles:
            with contextlib.suppress(Exception):
                handle.close()


def run_inspection(inspection_id: str, base_url: str = DEFAULT_BASE_URL) -> JsonDict:
    resp = _check(
        requests.post(
            f"{base_url}/inspections/{inspection_id}/run",
            params={"sync": "true"},
            timeout=_TIMEOUT,
        )
    )
    return cast(JsonDict, resp.json())


def download_report(
    inspection_id: str,
    save_path: str | Path,
    base_url: str = DEFAULT_BASE_URL,
) -> Path:
    target = Path(save_path)
    with requests.get(
        f"{base_url}/inspections/{inspection_id}/report",
        stream=True,
        timeout=_TIMEOUT,
    ) as resp:
        _check(resp)
        with target.open("wb") as f:
            for chunk in resp.iter_content(chunk_size=64 * 1024):
                if chunk:
                    f.write(chunk)
    return target
