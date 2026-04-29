"""Unit tests for glossary loading — no Azure, no network."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from app.services.glossary import load_glossary_text


def _settings(glossary_path: Path | None) -> MagicMock:
    m = MagicMock()
    m.glossary_path = glossary_path
    return m


def _patched(path: Path | None) -> str:
    load_glossary_text.cache_clear()
    with patch("app.services.glossary.get_settings", return_value=_settings(path)):
        result = load_glossary_text()
    load_glossary_text.cache_clear()
    return result


def test_returns_empty_when_path_is_none() -> None:
    assert _patched(None) == ""


def test_returns_empty_when_file_missing(tmp_path: Path) -> None:
    assert _patched(tmp_path / "no_such_file.txt") == ""


def test_skips_pdf_and_returns_empty(tmp_path: Path) -> None:
    p = tmp_path / "glossary.pdf"
    p.write_bytes(b"%PDF-1.4 fake")
    assert _patched(p) == ""


def test_reads_text_file(tmp_path: Path) -> None:
    p = tmp_path / "glossary.txt"
    p.write_text("crane hook sheave", encoding="utf-8")
    assert _patched(p) == "crane hook sheave"


def test_ignores_encoding_errors(tmp_path: Path) -> None:
    p = tmp_path / "glossary.txt"
    p.write_bytes(b"good text\xff\xfebad bytes")
    result = _patched(p)
    assert "good text" in result
