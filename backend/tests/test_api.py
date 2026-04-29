"""API endpoint tests — exercises every route the frontend calls."""

import json
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

import pytest
from app.api.inspections import _REGISTRY
from app.domain.inspection import InspectionStatus
from fastapi.testclient import TestClient

# Minimal bytes that pass extension checks (content is not validated on upload).
_TINY_JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"
_TINY_AUDIO = b"RIFF\x00\x00\x00\x00WAVEfmt "

_ONE_IMAGE_META = json.dumps([{"filename": "test.jpg", "captured_at": "2026-03-17T15:00:00Z"}])


def _upload(
    client: TestClient,
    *,
    image_name: str = "test.jpg",
    image_bytes: bytes = _TINY_JPEG,
    audio_name: str = "audio.wav",
    audio_bytes: bytes = _TINY_AUDIO,
    metadata: str = _ONE_IMAGE_META,
    extra_data: dict[str, str] | None = None,
) -> "pytest.Response":  # type: ignore[name-defined]
    data: dict[str, str] = {"metadata": metadata}
    if extra_data:
        data.update(extra_data)
    return client.post(
        "/inspections",
        data=data,
        files=[
            ("images", (image_name, BytesIO(image_bytes), "image/jpeg")),
            ("audio", (audio_name, BytesIO(audio_bytes), "audio/wav")),
        ],
    )


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


def test_health(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# GET /templates
# ---------------------------------------------------------------------------


class TestTemplates:
    def test_returns_empty_list(self, client: TestClient) -> None:
        with patch("app.api.templates.list_templates", return_value=[]):
            r = client.get("/templates")
        assert r.status_code == 200
        assert r.json() == []

    def test_returns_template_entries(self, client: TestClient) -> None:
        entries = [{"filename": "Report.xlsx", "path": "/data/Report.xlsx", "size_bytes": 1024}]
        with patch("app.api.templates.list_templates", return_value=entries):
            r = client.get("/templates")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["filename"] == "Report.xlsx"


# ---------------------------------------------------------------------------
# POST /inspections
# ---------------------------------------------------------------------------


class TestCreateInspection:
    def test_valid_upload_returns_201(self, client: TestClient) -> None:
        r = _upload(client)
        assert r.status_code == 201
        body = r.json()
        assert body["status"] == "created"
        assert len(body["images"]) == 1
        assert body["images"][0]["filename"] == "test.jpg"
        assert body["audio"]["filename"] == "audio.wav"

    def test_missing_images_returns_4xx(self, client: TestClient) -> None:
        # FastAPI returns 422 when a required File() field is absent entirely.
        r = client.post(
            "/inspections",
            data={"metadata": "[]"},
            files=[("audio", ("audio.wav", BytesIO(_TINY_AUDIO), "audio/wav"))],
        )
        assert r.status_code in (400, 422)

    def test_invalid_metadata_json_returns_400(self, client: TestClient) -> None:
        r = _upload(client, metadata="not-json")
        assert r.status_code == 400
        assert "not valid JSON" in r.json()["error"]["message"]

    def test_metadata_missing_for_image_returns_400(self, client: TestClient) -> None:
        r = _upload(client, metadata="[]")
        assert r.status_code == 400
        assert "Missing metadata" in r.json()["error"]["message"]

    def test_unsupported_image_extension_returns_400(self, client: TestClient) -> None:
        meta = json.dumps([{"filename": "scan.bmp", "captured_at": "2026-03-17T15:00:00Z"}])
        r = _upload(client, image_name="scan.bmp", metadata=meta)
        assert r.status_code == 400

    def test_unsupported_audio_extension_returns_400(self, client: TestClient) -> None:
        r = _upload(client, audio_name="audio.aac")
        assert r.status_code == 400

    def test_optional_template_filename_stored(self, client: TestClient) -> None:
        with patch("app.api.inspections.resolve_template"):
            r = _upload(
                client,
                extra_data={"template_filename": "Report.xlsx"},
            )
        assert r.status_code == 201
        assert r.json()["template_filename"] == "Report.xlsx"

    def test_error_envelope_shape(self, client: TestClient) -> None:
        r = _upload(client, metadata="bad")
        assert "error" in r.json()
        assert "code" in r.json()["error"]
        assert "message" in r.json()["error"]


# ---------------------------------------------------------------------------
# GET /inspections/{id}
# ---------------------------------------------------------------------------


class TestGetInspection:
    def test_unknown_id_returns_404(self, client: TestClient) -> None:
        r = client.get("/inspections/00000000-0000-0000-0000-000000000001")
        assert r.status_code == 404

    def test_returns_created_inspection(self, client: TestClient) -> None:
        create_r = _upload(client)
        inspection_id = create_r.json()["id"]
        r = client.get(f"/inspections/{inspection_id}")
        assert r.status_code == 200
        assert r.json()["id"] == inspection_id
        assert r.json()["status"] == "created"


# ---------------------------------------------------------------------------
# POST /inspections/{id}/run
# ---------------------------------------------------------------------------


class TestRunInspection:
    def test_unknown_id_returns_404(self, client: TestClient) -> None:
        r = client.post("/inspections/00000000-0000-0000-0000-000000000001/run")
        assert r.status_code == 404

    def test_sync_run_invokes_pipeline(self, client: TestClient) -> None:
        inspection_id = _upload(client).json()["id"]
        with patch("app.api.inspections.run_inspection") as mock_run:
            r = client.post(f"/inspections/{inspection_id}/run?sync=true")
        assert r.status_code == 200
        mock_run.assert_called_once()

    def test_async_run_returns_immediately(self, client: TestClient) -> None:
        inspection_id = _upload(client).json()["id"]
        with patch("app.api.inspections.run_inspection"):
            r = client.post(f"/inspections/{inspection_id}/run")
        assert r.status_code == 200

    def test_already_running_is_idempotent(self, client: TestClient) -> None:
        inspection_id = _upload(client).json()["id"]
        _REGISTRY[UUID(inspection_id)].status = InspectionStatus.RUNNING
        with patch("app.api.inspections.run_inspection") as mock_run:
            r = client.post(f"/inspections/{inspection_id}/run?sync=true")
        assert r.status_code == 200
        mock_run.assert_not_called()


# ---------------------------------------------------------------------------
# GET /inspections/{id}/report
# ---------------------------------------------------------------------------


class TestGetReport:
    def test_unknown_id_returns_404(self, client: TestClient) -> None:
        r = client.get("/inspections/00000000-0000-0000-0000-000000000001/report")
        assert r.status_code == 404

    def test_report_not_ready_returns_400(self, client: TestClient) -> None:
        inspection_id = _upload(client).json()["id"]
        r = client.get(f"/inspections/{inspection_id}/report")
        assert r.status_code == 400

    def test_report_streams_xlsx_when_completed(self, client: TestClient, tmp_path: Path) -> None:
        inspection_id = _upload(client).json()["id"]

        xlsx_bytes = b"PK\x03\x04fake-xlsx-content"
        report_path = tmp_path / "report.xlsx"
        report_path.write_bytes(xlsx_bytes)

        inspection = _REGISTRY[UUID(inspection_id)]
        inspection.status = InspectionStatus.COMPLETED
        inspection.report_path = report_path

        r = client.get(f"/inspections/{inspection_id}/report")
        assert r.status_code == 200
        assert "spreadsheetml" in r.headers["content-type"]
        assert r.content == xlsx_bytes
