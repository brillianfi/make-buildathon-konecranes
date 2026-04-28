"""Verify the frontend HTTP client speaks the backend's contract.

pytest-httpserver runs a real local HTTP server, so each test exercises the
full requests roundtrip (multipart encoding, query strings, streaming) — not
a stubbed `requests` object. If these pass, the client wires correctly.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pytest_httpserver import HTTPServer
from werkzeug.wrappers import Request, Response

import backend


@pytest.fixture
def base_url(httpserver: HTTPServer) -> str:
    return httpserver.url_for("").rstrip("/")


# ---------------- /templates ----------------

def test_list_templates_parses_payload(httpserver: HTTPServer, base_url: str) -> None:
    payload = [
        {"filename": "Inspection_Report.xlsx", "path": "/abs/x.xlsx", "size_bytes": 1024},
    ]
    httpserver.expect_request("/templates", method="GET").respond_with_json(payload)

    assert backend.list_templates(base_url) == payload


def test_list_templates_raises_on_5xx(httpserver: HTTPServer, base_url: str) -> None:
    httpserver.expect_request("/templates", method="GET").respond_with_json(
        {"detail": "boom"}, status=500
    )

    with pytest.raises(RuntimeError) as exc:
        backend.list_templates(base_url)

    assert "500" in str(exc.value)


# ---------------- POST /inspections ----------------

def test_create_inspection_sends_multipart_with_metadata(
    httpserver: HTTPServer, base_url: str, tmp_path: Path
) -> None:
    audio = tmp_path / "operator.m4a"
    audio.write_bytes(b"fake-audio-bytes")
    img1 = tmp_path / "DJI_001.JPG"
    img1.write_bytes(b"fake-image-1")
    img2 = tmp_path / "DJI_002.JPG"
    img2.write_bytes(b"fake-image-2")

    metadata = [
        {"filename": "DJI_001.JPG", "captured_at": "2024-05-17T12:30:45"},
        {"filename": "DJI_002.JPG", "captured_at": "2024-05-17T12:31:10"},
    ]

    captured: dict = {}

    def handler(request: Request) -> Response:
        captured["form"] = request.form.to_dict()
        captured["image_filenames"] = sorted(
            f.filename for f in request.files.getlist("images")
        )
        captured["audio_filename"] = request.files["audio"].filename
        captured["audio_bytes"] = request.files["audio"].read()
        return Response(
            json.dumps({"id": "abc-123", "status": "created"}),
            status=201,
            content_type="application/json",
        )

    httpserver.expect_request("/inspections", method="POST").respond_with_handler(handler)

    result = backend.create_inspection(
        audio_path=audio,
        image_paths=[img1, img2],
        metadata=metadata,
        template_filename="Inspection_Report.xlsx",
        base_url=base_url,
    )

    assert result == {"id": "abc-123", "status": "created"}
    assert captured["form"]["template_filename"] == "Inspection_Report.xlsx"
    assert json.loads(captured["form"]["metadata"]) == metadata
    assert captured["image_filenames"] == ["DJI_001.JPG", "DJI_002.JPG"]
    assert captured["audio_filename"] == "operator.m4a"
    assert captured["audio_bytes"] == b"fake-audio-bytes"


def test_create_inspection_propagates_validation_error(
    httpserver: HTTPServer, base_url: str, tmp_path: Path
) -> None:
    audio = tmp_path / "operator.m4a"
    audio.write_bytes(b"x")
    img = tmp_path / "img.jpg"
    img.write_bytes(b"x")

    httpserver.expect_request("/inspections", method="POST").respond_with_json(
        {"detail": "Missing metadata for image: img.jpg"}, status=400
    )

    with pytest.raises(RuntimeError) as exc:
        backend.create_inspection(
            audio_path=audio,
            image_paths=[img],
            metadata=[],
            template_filename="t.xlsx",
            base_url=base_url,
        )

    assert "400" in str(exc.value)
    assert "Missing metadata" in str(exc.value)


# ---------------- POST /inspections/{id}/run ----------------

def test_run_inspection_passes_sync_true(httpserver: HTTPServer, base_url: str) -> None:
    httpserver.expect_request(
        "/inspections/abc-123/run",
        method="POST",
        query_string={"sync": "true"},
    ).respond_with_json({"id": "abc-123", "status": "completed"})

    assert backend.run_inspection("abc-123", base_url=base_url)["status"] == "completed"


def test_run_inspection_propagates_failed_status(httpserver: HTTPServer, base_url: str) -> None:
    httpserver.expect_request(
        "/inspections/abc-123/run", method="POST", query_string={"sync": "true"}
    ).respond_with_json({"id": "abc-123", "status": "failed", "error": "transcription failed"})

    result = backend.run_inspection("abc-123", base_url=base_url)
    # The client doesn't raise on a logical "failed" status — that's the
    # caller's job (ReportWorker checks). But the HTTP roundtrip succeeds.
    assert result["status"] == "failed"
    assert result["error"] == "transcription failed"


# ---------------- GET /inspections/{id}/report ----------------

def test_download_report_streams_to_file(
    httpserver: HTTPServer, base_url: str, tmp_path: Path
) -> None:
    body = b"PK\x03\x04 fake-xlsx-binary-content"
    xlsx_mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    httpserver.expect_request(
        "/inspections/abc-123/report", method="GET"
    ).respond_with_data(body, content_type=xlsx_mime)

    out = tmp_path / "report.xlsx"
    returned = backend.download_report("abc-123", out, base_url=base_url)

    assert returned == out
    assert out.read_bytes() == body


def test_download_report_raises_when_not_ready(
    httpserver: HTTPServer, base_url: str, tmp_path: Path
) -> None:
    httpserver.expect_request(
        "/inspections/abc-123/report", method="GET"
    ).respond_with_json({"detail": "Report not ready"}, status=400)

    with pytest.raises(RuntimeError) as exc:
        backend.download_report("abc-123", tmp_path / "x.xlsx", base_url=base_url)

    assert "400" in str(exc.value)
