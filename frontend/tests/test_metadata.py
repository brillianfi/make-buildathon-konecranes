"""Image timestamp extraction — the only data analysis the frontend does."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

import backend


def _write_jpg(path: Path) -> None:
    Image.new("RGB", (8, 8), color="red").save(path, "JPEG")


def _write_jpg_with_datetime(path: Path, dt_str: str) -> None:
    """Save a JPEG with the DateTime EXIF tag (IFD0 tag 306)."""
    img = Image.new("RGB", (8, 8), color="blue")
    exif = img.getexif()
    exif[306] = dt_str  # DateTime tag in IFD0
    img.save(path, "JPEG", exif=exif.tobytes())


def test_dji_filename_yields_timestamp(tmp_path: Path) -> None:
    name = "DJI_20240517123045_0001_V.JPG"
    _write_jpg(tmp_path / name)

    records, skipped = backend.collect_from_folders([tmp_path])

    assert skipped == 0
    assert len(records) == 1
    assert records[0]["filename"] == name
    assert records[0]["captured_at"] == "2024-05-17T12:30:45"


def test_image_without_timestamp_is_skipped(tmp_path: Path) -> None:
    _write_jpg(tmp_path / "random.jpg")

    records, skipped = backend.collect_from_folders([tmp_path])

    assert records == []
    assert skipped == 1


def test_records_sorted_chronologically(tmp_path: Path) -> None:
    later = "DJI_20240517130000_0002_V.JPG"
    earlier = "DJI_20240517120000_0001_V.JPG"
    _write_jpg(tmp_path / later)
    _write_jpg(tmp_path / earlier)

    records, _ = backend.collect_from_folders([tmp_path])

    assert [r["filename"] for r in records] == [earlier, later]


def test_unsupported_extensions_are_ignored(tmp_path: Path) -> None:
    # .tif is intentionally outside the backend's accepted set.
    (tmp_path / "DJI_20240517120000_0001_V.tif").write_bytes(b"")
    _write_jpg(tmp_path / "DJI_20240517120000_0002_V.JPG")

    records, skipped = backend.collect_from_folders([tmp_path])

    assert len(records) == 1
    assert records[0]["filename"] == "DJI_20240517120000_0002_V.JPG"
    assert skipped == 0


def test_multiple_folders_deduplicate(tmp_path: Path) -> None:
    folder_a = tmp_path / "a"
    folder_a.mkdir()
    _write_jpg(folder_a / "DJI_20240517120000_0001_V.JPG")
    folder_b = tmp_path / "b"
    folder_b.mkdir()
    _write_jpg(folder_b / "DJI_20240517130000_0002_V.JPG")

    records, _ = backend.collect_from_folders([folder_a, folder_b])

    assert len(records) == 2


def test_missing_folder_is_ignored(tmp_path: Path) -> None:
    _write_jpg(tmp_path / "DJI_20240517120000_0001_V.JPG")

    records, _ = backend.collect_from_folders([tmp_path, tmp_path / "does-not-exist"])

    assert len(records) == 1


def test_exif_datetime_tag_yields_timestamp(tmp_path: Path) -> None:
    path = tmp_path / "photo.jpg"
    _write_jpg_with_datetime(path, "2026:03:17 14:22:00")

    records, skipped = backend.collect_from_folders([tmp_path])

    assert skipped == 0
    assert len(records) == 1
    assert records[0]["captured_at"] == "2026-03-17T14:22:00"


def test_exif_takes_priority_over_dji_filename(tmp_path: Path) -> None:
    # DJI filename says 12:00:00 but EXIF says 14:22:00 — EXIF wins.
    path = tmp_path / "DJI_20260317120000_0001_V.JPG"
    _write_jpg_with_datetime(path, "2026:03:17 14:22:00")

    records, _ = backend.collect_from_folders([tmp_path])

    assert records[0]["captured_at"] == "2026-03-17T14:22:00"


def test_same_folder_passed_twice_deduplicates(tmp_path: Path) -> None:
    _write_jpg(tmp_path / "DJI_20240517120000_0001_V.JPG")

    records, _ = backend.collect_from_folders([tmp_path, tmp_path])

    assert len(records) == 1
