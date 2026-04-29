# Drone Inspection Auto-Reporting

Demo project for the **MAKE Konecranes Buildathon 2026**. Turn drone inspection data — images plus a single operator audio commentary — into a structured Excel (`.xlsx`) inspection report.

| Component | Stack | What it does |
|---|---|---|
| **Frontend** | Python 3.12 · PyQt6 · uv | Desktop GUI. Drop / browse audio + image folders, extract EXIF (or DJI filename) timestamps, drive the backend pipeline, save the `.xlsx`. |
| **Backend** | Python 3.12 · FastAPI · uv | HTTP API. Transcribes audio with Whisper, runs per-image vision + report synthesis through Azure GPT, writes `.xlsx` with openpyxl. |

The frontend does **no AI / data analysis** — only image timestamp parsing. All transcription, vision, and report synthesis happens in the backend.

---

## Architecture

```
                       ┌──────────────────────────────────────┐
                       │                User                  │
                       └──────────────────────────────────────┘
                            │  drops audio + images        ▲
                            │  clicks Generate Report      │  saves .xlsx
                            ▼                              │  (or Open Folder)
                ┌──────────────────────────────┐
                │  Frontend  (PyQt6 desktop)   │
                │                              │
                │  • drag-drop OR browse       │
                │  • extract EXIF / DJI ts     │
                │  • progress + step UI        │
                │  • report location reveal    │
                └──────────────┬───────────────┘
                               │ HTTP (multipart / JSON)
                               │ default: http://localhost:8000
                               ▼
                ┌──────────────────────────────┐         ┌──────────────────────┐
                │  Backend  (FastAPI :8000)    │ ──────► │  Azure AI Foundry    │
                │                              │         │                      │
                │  POST /inspections           │         │  Whisper deployment  │
                │  POST /inspections/{id}/run  │ ◄────── │  GPT deployment      │
                │  GET  /inspections/{id}/report         │  (vision + synth)    │
                │                              │         │                      │
                │  → writes .xlsx via openpyxl │         └──────────────────────┘
                └──────────────────────────────┘
```

End-to-end flow on **Generate Report**:

1. Frontend uploads multipart (audio + images + image metadata) → `POST /inspections`.
2. Frontend triggers `POST /inspections/{id}/run?sync=true`. The backend:
   - **Transcribes** the audio via Whisper (per-segment timestamps).
   - **Correlates** each image to overlapping transcript segments via EXIF/DJI capture time.
   - **Vision pass:** for every image, calls GPT with the image + operator commentary + glossary → structured `Finding`.
   - **Synthesis:** GPT turns findings + transcript + template-as-text into a workbook JSON.
   - **Writes** the `.xlsx` via openpyxl.
3. Frontend streams the result via `GET /inspections/{id}/report` and lets the user save it.

---

## Prerequisites

- **Python 3.12**
- **[uv](https://docs.astral.sh/uv/)** (`brew install uv` or [other installs](https://docs.astral.sh/uv/getting-started/installation/))
- **Azure OpenAI** access with two deployments (Whisper + a GPT model)

The frontend additionally needs PyQt6 — `uv sync` in `frontend/` handles it.

---

## Quickstart — run the whole project

### 1. Configure secrets (once)

```bash
cp .env.example .env       # then edit .env with real Azure values
```

The backend fails to start if any required key is empty. See [`backend/README.md`](backend/README.md#environment-variables) for the full env-var table.

### 2. Start the backend (terminal 1)

```bash
cd backend
make install               # uv sync
make dev                   # http://localhost:8000  ·  docs at /docs
```

Sanity-check it's up:

```bash
curl http://localhost:8000/health     # → {"status":"ok"}
```

Optional smoke check that exercises Whisper + GPT against demo audio/image:

```bash
PYTHONPATH=. uv run python scripts/smoke_all.py
```

### 3. Start the frontend (terminal 2)

```bash
cd frontend
make install               # uv sync
make run                   # opens the desktop GUI
```

Override the backend URL with `BACKEND_URL=https://… make run` if it's not on `localhost:8000`.

### 4. Use the GUI

1. Drop or browse **one audio file** (`.m4a / .mp3 / .wav / .ogg / .flac / .webm`).
2. Drop or browse **one or more image folders** (`.jpg / .jpeg / .png / .webp`). Capture time is read from EXIF; the DJI filename pattern (`DJI_YYYYMMDDHHMMSS_*.JPG`) is the fallback.
3. Optionally pick a **report template** from the dropdown (loaded from the backend's `GET /templates`). Leave on **(none)** to let the backend build a default workbook.
4. Click **Generate Report**. The progress bar + step list show: *Upload → Run pipeline → Download report.*
5. Click **Save Report…** to choose where to write the `.xlsx`. Use **Open Folder** to reveal it in your file manager.

---

## Project layout

```
.
├── README.md             ← you are here
├── PLAN.md               ← original buildathon plan
├── .env.example          ← Azure key template (copy to .env)
├── data/                 ← demo audio / images / templates / glossary (gitignored)
│
├── backend/              ← FastAPI service — see backend/README.md
│   ├── app/
│   │   ├── api/          ←   /health · /templates · /inspections
│   │   ├── services/     ←   transcription · vision · report_builder · pipeline
│   │   ├── clients/      ←   Azure OpenAI clients
│   │   └── …
│   ├── scripts/          ← smoke checks
│   ├── pyproject.toml · uv.lock · Dockerfile · Makefile
│
└── frontend/             ← PyQt6 desktop app — see frontend/README.md
    ├── app.py            ← GUI (DropArea, ReportWorker, ReportApp)
    ├── backend.py        ← image timestamp extraction + HTTP client
    ├── tests/            ← pytest-httpserver API contract tests + metadata tests
    └── pyproject.toml · uv.lock · Makefile
```

---

## Where to read more

- **API reference and per-endpoint details:** [`backend/README.md`](backend/README.md)
- **GUI behaviour, BACKEND_URL config, tests:** [`frontend/README.md`](frontend/README.md)
- **Original architecture rationale:** [`PLAN.md`](PLAN.md)

---

## Public-repo safety

This repository is public. **Never commit:**

- `.env` with real keys
- Anything under `data/` or `backend/var/`
- Generated reports (may contain customer/site identifiers)

`.gitignore` enforces the file-level rules; secrets are only ever read from `.env` via `pydantic-settings`.
