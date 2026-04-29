"""Unit tests for image-to-transcript-segment correlation."""

from datetime import UTC, datetime
from pathlib import Path

from app.domain.inspection import ImageAsset
from app.domain.transcript import Transcript, TranscriptSegment
from app.services.correlation import commentary_for_image, find_segments_for_image

_ANCHOR = datetime(2026, 3, 17, 15, 0, 0, tzinfo=UTC)


def _image(dt: datetime, filename: str = "img.jpg") -> ImageAsset:
    return ImageAsset(filename=filename, path=Path(filename), captured_at=dt, location=None)


def _seg(start: float, end: float, text: str) -> TranscriptSegment:
    return TranscriptSegment(start=start, end=end, text=text)


def _transcript(*segs: TranscriptSegment) -> Transcript:
    return Transcript(text="", segments=list(segs))


def _capture(offset_s: float) -> datetime:
    from datetime import timedelta

    return _ANCHOR + timedelta(seconds=offset_s)


class TestFindSegmentsForImage:
    def test_exact_overlap(self) -> None:
        seg = _seg(8.0, 12.0, "hello")
        result = find_segments_for_image(_capture(10), _ANCHOR, [seg])
        assert result == [seg]

    def test_within_default_window_early(self) -> None:
        # image at offset 3s; segment starts at 6s → 6-5=1 ≤ 3 ✓
        seg = _seg(6.0, 10.0, "soon")
        result = find_segments_for_image(_capture(3), _ANCHOR, [seg])
        assert result == [seg]

    def test_within_default_window_late(self) -> None:
        # image at offset 20s; segment ends at 16s → 16+5=21 ≥ 20 ✓
        seg = _seg(14.0, 16.0, "close")
        result = find_segments_for_image(_capture(20), _ANCHOR, [seg])
        assert result == [seg]

    def test_outside_window(self) -> None:
        # image at offset 30s; segment ends at 20s → 20+5=25 < 30 → no match
        seg = _seg(15.0, 20.0, "far")
        assert find_segments_for_image(_capture(30), _ANCHOR, [seg]) == []

    def test_multiple_matches(self) -> None:
        segs = [_seg(5.0, 15.0, "A"), _seg(8.0, 12.0, "B"), _seg(50.0, 60.0, "C")]
        result = find_segments_for_image(_capture(10), _ANCHOR, segs)
        assert result == [segs[0], segs[1]]

    def test_custom_window(self) -> None:
        seg = _seg(14.0, 16.0, "edge")
        # Narrow window: 16+2=18 < 20 → no match
        assert find_segments_for_image(_capture(20), _ANCHOR, [seg], window_seconds=2.0) == []
        # Default window: 16+5=21 ≥ 20 → match
        assert find_segments_for_image(_capture(20), _ANCHOR, [seg]) == [seg]

    def test_empty_segment_list(self) -> None:
        assert find_segments_for_image(_capture(10), _ANCHOR, []) == []

    def test_image_before_anchor(self) -> None:
        # Negative offset: image captured before audio started, window still applies.
        seg = _seg(0.0, 3.0, "intro")
        result = find_segments_for_image(_capture(-2), _ANCHOR, [seg])
        assert result == [seg]


class TestCommentaryForImage:
    def test_returns_empty_without_transcript(self) -> None:
        assert commentary_for_image(_image(_capture(10)), None, _ANCHOR) == ""

    def test_returns_empty_without_anchor(self) -> None:
        ts = _transcript(_seg(8.0, 12.0, "hello"))
        assert commentary_for_image(_image(_capture(10)), ts, None) == ""

    def test_joins_matched_segments(self) -> None:
        ts = _transcript(_seg(8.0, 12.0, "hello"), _seg(9.0, 11.0, " world "))
        result = commentary_for_image(_image(_capture(10)), ts, _ANCHOR)
        assert result == "hello world"

    def test_returns_empty_when_no_overlap(self) -> None:
        ts = _transcript(_seg(0.0, 5.0, "early"))
        assert commentary_for_image(_image(_capture(60)), ts, _ANCHOR) == ""

    def test_strips_whitespace_from_segments(self) -> None:
        ts = _transcript(_seg(8.0, 12.0, "  trim me  "))
        result = commentary_for_image(_image(_capture(10)), ts, _ANCHOR)
        assert result == "trim me"
