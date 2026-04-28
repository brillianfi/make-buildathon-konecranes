# Drone Inspection Frontend

PyQt6 desktop client for the [drone inspection backend](../backend/README.md). The user supplies one audio file and one or more image folders; the app extracts capture timestamps from EXIF (or DJI filenames), uploads everything to the backend, runs the pipeline, and lets the user save the generated `.xlsx` report.

The frontend does **no AI / data analysis** — only image timestamp parsing. All transcription, vision, and report synthesis happens in the backend.

---

## Quick start

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/). The backend should be reachable at `BACKEND_URL` (default `http://localhost:8000`) before launching.

```bash
make install   # uv sync
make run       # launch the desktop app
```

If the backend is on another host:

```bash
BACKEND_URL=https://api.example.com make run
```

For the full project setup (backend + frontend), see the [root README](../README.md).

---

## What the GUI does

The window is laid out as a single column:

1. **Audio drop area** + **Browse audio file…** button. Accepts `.m4a / .mp3 / .wav / .ogg / .flac / .webm`.
2. **Image folder drop area** + **Browse folder…** button. Drop multiple folders at once; the app dedupes paths and rescans on each drop. Capture time is read from EXIF `DateTimeOriginal` / `DateTime`; the DJI filename pattern `DJI_YYYYMMDDHHMMSS_*.JPG` is the fallback. Images without any recoverable timestamp are skipped (count is shown in the label).
3. **Template dropdown** (loaded from `GET /templates`) with an always-present `(none — let backend decide)` entry — template selection is **optional**. **Refresh** re-fetches the list.
4. **Generate Report** kicks off the pipeline in a `QThread` so the UI stays responsive.
5. **Progress bar (indeterminate)** and a **step list** that updates live:
   - `○  Upload audio + images` (pending / gray)
   - `▶  Run pipeline (transcribe + analyse + build xlsx)` (running / blue)
   - `✓  Download report` (done / green) or `✗ …` (failed / red)
6. **Report location row** — shown once a report exists. Selectable text path + **Open Folder** button (reveals the file in Finder / Explorer / file manager). Color-coded: gray for the temp staging file, green once the user saves it.
7. **Save Report…** writes the `.xlsx` to a user-chosen path.
8. **Status line** at the bottom shows the backend URL, current step (`Step 2/3: Run pipeline…`), or final state (`Report ready.` / `Report saved.` / `Failed.`).

---

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `BACKEND_URL` | `http://localhost:8000` | Base URL of the FastAPI backend. |

---

## Backend endpoints used

| Method | Path | When |
|---|---|---|
| `GET` | `/templates` | At launch and when **Refresh** is clicked. |
| `POST` | `/inspections` | When **Generate Report** is clicked — uploads multipart audio + images + metadata. |
| `POST` | `/inspections/{id}/run?sync=true` | Immediately after upload — blocks until the pipeline finishes. |
| `GET` | `/inspections/{id}/report` | After completion — streams the generated `.xlsx`. |

Multipart contract for `POST /inspections`:

| Field | Notes |
|---|---|
| `template_filename` | optional · filename from `GET /templates`, or empty |
| `metadata` | JSON array `[{filename, captured_at}]`, one entry per image |
| `images` | one part per image (`.jpg / .jpeg / .png / .webp`) |
| `audio` | one part (`.m4a / .mp3 / .wav / .ogg / .flac / .webm`) |

`metadata[].filename` must match the multipart filename byte-for-byte — the GUI guarantees this because both come from the same `Path.name`.

See [`backend/README.md`](../backend/README.md) for the full API reference.

---

## Layout

```
frontend/
├── app.py                  # PyQt6 GUI: DropArea · ReportWorker · ReportApp
├── backend.py              # image timestamp extraction + HTTP client
├── tests/
│   ├── test_backend_api.py # 8 API-contract tests (pytest-httpserver)
│   └── test_metadata.py    # 6 EXIF / DJI filename extraction tests
├── pyproject.toml · uv.lock
├── Makefile
└── .python-version
```

---

## Tests

The API tests run a real local HTTP server (`pytest-httpserver`) and exercise the full `requests` roundtrip — multipart encoding, query strings, streaming downloads, error handling. If they pass, the frontend speaks the backend's contract correctly. **The backend does not need to be running** for `make test`.

```bash
make test       # pytest
make check      # lint + typecheck + test
```

Coverage:
- `tests/test_backend_api.py` — every endpoint the GUI calls (templates, create, run, report) plus error paths
- `tests/test_metadata.py` — DJI filename / EXIF parsing, sorting, dedup, missing-folder handling

---

## Quality gates

```bash
make lint        # ruff check + ruff format --check
make typecheck   # mypy --strict on app.py + backend.py
make check       # lint + typecheck + test
make fmt         # ruff format + ruff check --fix
```

`mypy --strict` covers `app.py` and `backend.py`. PyQt6 / Pillow imports are allowed to be untyped via the `mypy.overrides` block in `pyproject.toml`.

---

## Make targets

| Target | What it does |
|---|---|
| `make install` | `uv sync` (creates `.venv`, locks deps) |
| `make run` | Launch the desktop GUI |
| `make test` | Run pytest |
| `make lint` | Ruff lint + format check |
| `make typecheck` | mypy --strict |
| `make fmt` | Auto-format + auto-fix lint |
| `make check` | lint + typecheck + test |
| `make clean` | Remove `.venv` and tool caches |

---

## Notes

- The pipeline runs synchronously (`?sync=true`) for simplicity — the worker thread keeps the UI from freezing during the 30–120 s wait. The async API (`POST /run` without `sync=true` plus polling `GET /inspections/{id}`) is available on the backend but not used here.
- The GUI uses one OS-level temp file as a staging buffer for the downloaded `.xlsx`; the user picks the final destination via **Save Report…**. The location row distinguishes "Staged at (temporary)" from "Saved to" so the user always knows where the report lives.
- No customer / inspection assets are persisted by the frontend — uploads come from the user's filesystem and reports are saved wherever the user chooses.
