# Drone Inspection Frontend

PyQt6 desktop client for the [drone inspection backend](../backend/README.md). The user drops one audio file and one or more image folders, the app extracts capture timestamps from EXIF (or DJI filenames), uploads everything to the backend, runs the pipeline, and downloads the generated `.xlsx` report.

The frontend does **no AI / data analysis** — only image timestamp parsing. All transcription, vision, and report synthesis happens in the backend.

---

## Quick start

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
make install   # uv sync
make run       # launch the app

# Make sure the backend is reachable first:
#   cd ../backend && make dev   # http://localhost:8000
```

---

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `BACKEND_URL` | `http://localhost:8000` | Base URL of the FastAPI backend. |

```bash
BACKEND_URL=https://api.example.com make run
```

---

## What the GUI does

1. **Drop one audio file** (`.m4a / .mp3 / .wav / .ogg / .flac / .webm`).
2. **Drop one or more image folders.** Capture time is read from EXIF `DateTimeOriginal` / `DateTime`; if missing, the DJI filename pattern `DJI_YYYYMMDDHHMMSS_*.JPG` is used. Images without any recoverable timestamp are skipped (and counted in the status line).
3. **Pick a template** from the dropdown (loaded from the backend's `GET /templates`). Click **Refresh** if you just added one.
4. **Generate Report.** Runs in a `QThread`, so the UI stays responsive while the backend transcribes + analyses (~30–120s).
5. **Save Report…** writes the `.xlsx` to the path of your choice.

---

## Backend endpoints used

| Method | Path | When |
|---|---|---|
| `GET` | `/templates` | On startup and when **Refresh** is clicked. |
| `POST` | `/inspections` | When **Generate Report** is clicked — uploads multipart audio + images + metadata. |
| `POST` | `/inspections/{id}/run?sync=true` | Immediately after upload — blocks until the pipeline finishes. |
| `GET` | `/inspections/{id}/report` | After the run completes — streams the generated `.xlsx`. |

Multipart contract for `POST /inspections`:

| Field | Notes |
|---|---|
| `template_filename` | filename from `GET /templates` |
| `metadata` | JSON array `[{filename, captured_at}]`, one entry per image |
| `images` | one part per image (`.jpg/.jpeg/.png/.webp`) |
| `audio` | one part (`.m4a/.mp3/.wav/.ogg/.flac/.webm`) |

`metadata[].filename` must match the multipart filename byte-for-byte — the GUI guarantees this because it derives both from the same `Path.name`.

See [`backend/README.md`](../backend/README.md) for the full API reference.

---

## Layout

```
frontend/
├── app.py              # PyQt6 GUI (DropArea, ReportWorker, ReportApp)
├── backend.py          # image timestamp extraction + HTTP client
├── tests/
│   ├── test_backend_api.py   # API contract tests via pytest-httpserver
│   └── test_metadata.py      # EXIF / DJI filename extraction
├── pyproject.toml
├── uv.lock
├── Makefile
└── .python-version
```

---

## Tests

The API tests run a real local HTTP server (`pytest-httpserver`) and exercise the full `requests` roundtrip — multipart encoding, query strings, streaming downloads, error handling. If they pass, the frontend speaks the backend's contract correctly.

```bash
make test         # pytest
make check        # lint + typecheck + test
```

Coverage:
- `tests/test_backend_api.py` — 8 tests verifying every endpoint the GUI calls
- `tests/test_metadata.py` — 6 tests for image timestamp extraction

---

## Quality gates

```bash
make lint        # ruff check + ruff format --check
make typecheck   # mypy --strict
make check       # lint + typecheck + test
make fmt         # ruff format + ruff check --fix
```

`mypy --strict` covers `app.py` and `backend.py`. PyQt6 / Pillow imports are allowed to be untyped.

---

## Notes

- The pipeline runs synchronously (`sync=true`) for simplicity — the worker thread keeps the UI from freezing during the wait. The async `POST /run` (no `sync=true`) and polling `GET /inspections/{id}` are available on the backend but not used here.
- The GUI uses one OS-level temp file as a staging buffer for the downloaded `.xlsx`; the user picks the final destination via **Save Report…**.
- No customer / inspection assets are persisted by the frontend — uploads come from the user's filesystem and reports are saved wherever the user chooses.
