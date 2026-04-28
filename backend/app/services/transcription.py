from pathlib import Path

from tenacity import retry, stop_after_attempt, wait_exponential

from app.clients.azure_openai import get_whisper_client
from app.core.config import get_settings
from app.core.logging import get_logger
from app.domain.transcript import Transcript, TranscriptSegment

log = get_logger(__name__)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10), reraise=True)
def transcribe(
    audio_path: Path,
    *,
    prompt: str | None = None,
    language: str | None = None,
) -> Transcript:
    """Run Whisper on a single audio file, returning timestamped segments.

    `language` is an ISO 639-1 code (e.g. "en", "fi"). When None or "auto",
    Whisper auto-detects. Auto-detection can mis-classify accented English as
    Finnish on this corpus, so passing the language explicitly is recommended.

    Files >25MB will fail at the API; chunking is intentionally out of scope for
    the prototype. Operator audio is typically short enough.
    """
    settings = get_settings()
    client = get_whisper_client()
    log.info(
        "transcribe.start",
        file=str(audio_path),
        deployment=settings.azure_openai_whisper_deployment,
        language=language or "auto",
    )

    use_lang = language if language and language.lower() != "auto" else None

    with audio_path.open("rb") as f:
        if use_lang is not None:
            result = client.audio.transcriptions.create(
                model=settings.azure_openai_whisper_deployment,
                file=f,
                response_format="verbose_json",
                timestamp_granularities=["segment"],
                prompt=prompt or "",
                language=use_lang,
            )
        else:
            result = client.audio.transcriptions.create(
                model=settings.azure_openai_whisper_deployment,
                file=f,
                response_format="verbose_json",
                timestamp_granularities=["segment"],
                prompt=prompt or "",
            )

    raw = result.model_dump() if hasattr(result, "model_dump") else dict(result)
    segments = [
        TranscriptSegment(start=s["start"], end=s["end"], text=s["text"].strip())
        for s in raw.get("segments", [])
    ]
    transcript = Transcript(
        language=raw.get("language"),
        duration=raw.get("duration"),
        text=raw.get("text", ""),
        segments=segments,
    )
    log.info(
        "transcribe.done",
        file=str(audio_path),
        language=transcript.language,
        segments=len(transcript.segments),
    )
    return transcript
