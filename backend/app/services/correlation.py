from datetime import datetime

from app.domain.inspection import ImageAsset
from app.domain.transcript import Transcript, TranscriptSegment


def find_segments_for_image(
    image_capture: datetime,
    audio_anchor: datetime,
    segments: list[TranscriptSegment],
    *,
    window_seconds: float = 5.0,
) -> list[TranscriptSegment]:
    """Return transcript segments overlapping the image's capture moment.

    Audio is assumed to start at `audio_anchor` (wall-clock). Each segment's
    [start, end] is offset from that anchor and compared with the image's
    capture time, with a +/- tolerance window.
    """
    offset = (image_capture - audio_anchor).total_seconds()
    return [s for s in segments if (s.start - window_seconds) <= offset <= (s.end + window_seconds)]


def commentary_for_image(
    image: ImageAsset,
    transcript: Transcript | None,
    audio_anchor: datetime | None,
) -> str:
    """Return the operator's commentary likely associated with an image."""
    if transcript is None or audio_anchor is None:
        return ""
    matched = find_segments_for_image(image.captured_at, audio_anchor, transcript.segments)
    return " ".join(s.text.strip() for s in matched if s.text.strip())
