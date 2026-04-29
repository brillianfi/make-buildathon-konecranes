"""Unit tests for template listing and resolution."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from app.services.template_loader import list_templates, resolve_template


def _settings(templates_dir: Path) -> MagicMock:
    m = MagicMock()
    m.templates_dir = templates_dir
    return m


class TestListTemplates:
    def test_missing_directory_returns_empty(self, tmp_path: Path) -> None:
        missing = tmp_path / "nonexistent"
        with patch("app.services.template_loader.get_settings", return_value=_settings(missing)):
            assert list_templates() == []

    def test_empty_directory_returns_empty(self, tmp_path: Path) -> None:
        d = tmp_path / "templates"
        d.mkdir()
        with patch("app.services.template_loader.get_settings", return_value=_settings(d)):
            assert list_templates() == []

    def test_returns_xlsx_files_sorted(self, tmp_path: Path) -> None:
        d = tmp_path / "templates"
        d.mkdir()
        (d / "B_Report.xlsx").write_bytes(b"PK")
        (d / "A_Report.xlsx").write_bytes(b"PK")
        with patch("app.services.template_loader.get_settings", return_value=_settings(d)):
            result = list_templates()
        assert [r.filename for r in result] == ["A_Report.xlsx", "B_Report.xlsx"]

    def test_skips_excel_lock_files(self, tmp_path: Path) -> None:
        d = tmp_path / "templates"
        d.mkdir()
        (d / "Report.xlsx").write_bytes(b"PK")
        (d / "~$Report.xlsx").write_bytes(b"PK")
        with patch("app.services.template_loader.get_settings", return_value=_settings(d)):
            result = list_templates()
        assert len(result) == 1
        assert result[0].filename == "Report.xlsx"

    def test_skips_non_xlsx_files(self, tmp_path: Path) -> None:
        d = tmp_path / "templates"
        d.mkdir()
        (d / "Report.xlsx").write_bytes(b"PK")
        (d / "notes.txt").write_text("ignore me")
        with patch("app.services.template_loader.get_settings", return_value=_settings(d)):
            result = list_templates()
        assert len(result) == 1

    def test_reports_correct_size(self, tmp_path: Path) -> None:
        d = tmp_path / "templates"
        d.mkdir()
        content = b"X" * 512
        (d / "Report.xlsx").write_bytes(content)
        with patch("app.services.template_loader.get_settings", return_value=_settings(d)):
            result = list_templates()
        assert result[0].size_bytes == 512


class TestResolveTemplate:
    def test_valid_file_resolves(self, tmp_path: Path) -> None:
        d = tmp_path / "templates"
        d.mkdir()
        p = d / "Report.xlsx"
        p.write_bytes(b"PK")
        with patch("app.services.template_loader.get_settings", return_value=_settings(d)):
            resolved = resolve_template("Report.xlsx")
        assert resolved == p.resolve()

    def test_nonexistent_file_raises_file_not_found(self, tmp_path: Path) -> None:
        d = tmp_path / "templates"
        d.mkdir()
        with (
            patch("app.services.template_loader.get_settings", return_value=_settings(d)),
            pytest.raises(FileNotFoundError),
        ):
            resolve_template("missing.xlsx")

    def test_path_traversal_is_blocked(self, tmp_path: Path) -> None:
        d = tmp_path / "templates"
        d.mkdir()
        secret = tmp_path / "secret.xlsx"
        secret.write_bytes(b"PK")
        with (
            patch("app.services.template_loader.get_settings", return_value=_settings(d)),
            pytest.raises(ValueError, match="not under templates dir"),
        ):
            resolve_template("../secret.xlsx")

    def test_absolute_path_outside_dir_is_blocked(self, tmp_path: Path) -> None:
        d = tmp_path / "templates"
        d.mkdir()
        secret = tmp_path / "secret.xlsx"
        secret.write_bytes(b"PK")
        with (
            patch("app.services.template_loader.get_settings", return_value=_settings(d)),
            pytest.raises((ValueError, FileNotFoundError)),
        ):
            resolve_template(str(secret))
