from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger(__name__)


@lru_cache
def load_glossary_text() -> str:
    """Load the crane glossary as plain text.

    Prototype: read it raw if it's a text-like file. PDF parsing is intentionally
    out of scope; if the configured path is a PDF, return an empty string and
    rely on the LLM's general crane-domain knowledge instead.
    """
    settings = get_settings()
    path = settings.glossary_path
    if path is None:
        return ""
    p = Path(path)
    if not p.exists():
        log.warning("glossary.missing", path=str(p))
        return ""
    if p.suffix.lower() == ".pdf":
        log.info("glossary.skipped_pdf", path=str(p))
        return ""
    try:
        return p.read_text(encoding="utf-8", errors="ignore")
    except OSError as exc:
        log.warning("glossary.read_failed", path=str(p), error=str(exc))
        return ""
