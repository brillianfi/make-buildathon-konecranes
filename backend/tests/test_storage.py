"""Unit tests for local filesystem storage."""

import io
from pathlib import Path
from uuid import UUID, uuid4

from app.storage.local import LocalStorage

_ID = UUID("12345678-1234-5678-1234-567812345678")


def _storage(tmp_path: Path) -> LocalStorage:
    return LocalStorage(tmp_path / "var")


class TestLocalStorage:
    def test_init_creates_root_dir(self, tmp_path: Path) -> None:
        root = tmp_path / "new" / "root"
        LocalStorage(root)
        assert root.is_dir()

    def test_inspection_dir_is_created(self, tmp_path: Path) -> None:
        storage = _storage(tmp_path)
        d = storage.inspection_dir(_ID)
        assert d.is_dir()
        assert str(_ID) in str(d)

    def test_save_upload_writes_content(self, tmp_path: Path) -> None:
        storage = _storage(tmp_path)
        content = b"fake-image-bytes"
        saved = storage.save_upload(_ID, "images", "photo.jpg", io.BytesIO(content))
        assert saved.read_bytes() == content
        assert saved.name == "photo.jpg"

    def test_save_upload_strips_path_components(self, tmp_path: Path) -> None:
        storage = _storage(tmp_path)
        saved = storage.save_upload(_ID, "images", "../../evil.jpg", io.BytesIO(b"x"))
        assert saved.name == "evil.jpg"
        assert storage.root in saved.parents

    def test_report_path_is_inside_inspection_dir(self, tmp_path: Path) -> None:
        storage = _storage(tmp_path)
        p = storage.report_path(_ID)
        assert p.name == "report.xlsx"
        assert str(_ID) in str(p)

    def test_separate_inspections_are_isolated(self, tmp_path: Path) -> None:
        storage = _storage(tmp_path)
        id_a, id_b = uuid4(), uuid4()
        storage.save_upload(id_a, "images", "img.jpg", io.BytesIO(b"A"))
        storage.save_upload(id_b, "images", "img.jpg", io.BytesIO(b"B"))
        assert storage.inspection_dir(id_a) != storage.inspection_dir(id_b)
