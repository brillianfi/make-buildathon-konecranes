# Backend Action Plan — Drone Inspection Auto-Reporting

Backend that turns drone inspection data (images + operator audio commentary) into a structured **Excel (.xlsx) report** by combining OpenAI Whisper transcription with Azure-hosted GPT vision/synthesis. Report templates live in `data/4 Report Templates/` and are passed verbatim to the LLM as extra context (no custom template engine, no parsing logic beyond a basic text extraction).

**Scope for this plan:** backend prototype only. Frontend is owned by another team. Tests will be left as empty placeholders (structure scaffolded, no real assertions).

**Repo is public — secret/data hygiene is a hard requirement.**

## Repo state observed

- `backend/` is empty (only `.gitkeep`).
- Demo data on disk:
  - `data/1 Inspection Pictures/...` — DJI `.JPG` files with EXIF capture timestamps.
  - `data/2 Inspection Audios/...` — `.m4a` files (English + Finnish).
  - `data/4 Report Templates/` — empty.
  - `data/6 Industrial Crane Dictionary/Konecranes_Crane_Dictionary_EN_FI.pdf` — terminology bias source.
- `.env` exists (empty), `.env.example` has only `LLM_API_KEY` (will be replaced).
- `.gitignore` is minimal (`/data`, `.env`).

## 1. Stack

- **Python 3.12 + FastAPI** — async, first-class OpenAI SDK, Pydantic for typed I/O, easy multipart uploads.
- **uv** for dependency + venv management (fast, reproducible `uv.lock`).
- **OpenAI SDK** — used in two configurations:
  - `OpenAI(api_key=...)` for Whisper transcription (`whisper-1`).
  - `AzureOpenAI(api_key=..., azure_endpoint=..., api_version=...)` for GPT vision + synthesis (deployment name configurable).
- **openpyxl** — read templates from `data/4 Report Templates/` (flatten cells/sheets to text for LLM context) and write the final `.xlsx` report.
- **Pillow + piexif** to read image EXIF (capture timestamp) for audio↔image correlation.
- **structlog** for structured JSON logs; **tenacity** for retries on API calls.

## 2. Architecture (layered)

```
backend/
├── app/
│   ├── api/                # FastAPI routers (HTTP boundary only)
│   │   ├── health.py
│   │   ├── inspections.py  # POST upload, GET status, GET report
│   │   └── templates.py    # list/get templates
│   ├── core/
│   │   ├── config.py       # Pydantic Settings (env-driven)
│   │   ├── logging.py
│   │   └── errors.py       # typed exceptions + handlers
│   ├── domain/             # Pydantic models — pure, no I/O
│   │   ├── inspection.py   # Inspection, ImageAsset, AudioAsset
│   │   ├── transcript.py   # Transcript, Segment(start,end,text)
│   │   └── report.py       # ReportTemplate, ReportDraft, Section
│   ├── clients/            # External SDK wrappers (auth + retry)
│   │   ├── openai_whisper.py   # OpenAI client for Whisper
│   │   └── azure_gpt.py        # AzureOpenAI client for GPT-4o
│   ├── services/           # Business logic, no FastAPI imports
│   │   ├── transcription.py    # Whisper wrapper (chunking >25MB, lang hint)
│   │   ├── vision.py           # GPT image description + finding extraction
│   │   ├── correlation.py      # match images↔audio segments by timestamp
│   │   ├── template_loader.py  # read xlsx templates from data/, flatten to text
│   │   ├── report_builder.py   # findings + transcript + template → JSON → xlsx
│   │   ├── xlsx_writer.py      # openpyxl: structured JSON → .xlsx file
│   │   └── glossary.py         # Konecranes crane dictionary loader
│   ├── storage/
│   │   ├── base.py         # Protocol: save/load/list assets
│   │   └── local.py        # local-fs impl (writes under backend/var/)
│   └── main.py             # FastAPI app factory
├── tests/                  # Placeholders only — empty structure
│   └── .gitkeep
├── pyproject.toml
├── uv.lock
├── Dockerfile
├── Makefile                # make dev / lint / fmt
└── .pre-commit-config.yaml
```

## 3. Pipeline

1. **Ingest** — `POST /inspections` accepts multipart: N images + 1+ audio files + `template_id`. Persist via storage layer to `backend/var/inspections/<id>/` (gitignored). In-memory registry for prototype.
2. **Transcribe** — `services/transcription.py` calls Whisper (OpenAI key) with `response_format="verbose_json"` for per-segment timestamps. Auto-chunk if >25 MB. Detect language; pass crane glossary as `prompt` to bias terminology.
3. **Extract image timestamps** — read EXIF `DateTimeOriginal`. Anchor first audio start to first photo (or accept user-supplied offset).
4. **Correlate** — `correlation.py` maps each image to the audio segment(s) covering its capture time (± window). Output `List[CorrelatedFinding]`.
5. **Vision pass** — `vision.py` sends `(image, operator_commentary, glossary_snippet)` to Azure GPT with a structured-output schema (`Finding{component, condition, severity, recommendation}`). Parallelized with `asyncio.gather` + semaphore.
6. **Synthesize** — `report_builder.py` feeds findings + raw transcript + template into a final Azure GPT call that fills the Jinja2 template. Returns `ReportDraft` (Markdown).
7. **Deliver** — `GET /inspections/{id}/report?format=md|html`.

## 4. Configuration — two API keys

Two distinct providers; both keys are loaded via `pydantic-settings` from `.env`. Keys are **never** logged or echoed in error responses.

`.env.example` (committed, no real values):

```
# OpenAI (used for Whisper only)
OPENAI_API_KEY=
WHISPER_MODEL=whisper-1

# Azure OpenAI (used for GPT vision + report synthesis)
AZURE_OPENAI_API_KEY=
AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com
AZURE_OPENAI_API_VERSION=2024-08-01-preview
AZURE_OPENAI_GPT_DEPLOYMENT=gpt-4o

# App
LOG_LEVEL=INFO
STORAGE_DIR=./var
MAX_UPLOAD_MB=200
CORS_ORIGINS=http://localhost:5173
```

## 5. Public-repo safety — gitignore + non-output policy

The repo is public. The following must never be committed and must never be echoed back in any conversation, log, or response:

- Real API keys / secrets (`OPENAI_API_KEY`, `AZURE_OPENAI_API_KEY`, etc.).
- Customer/inspection assets under `data/` and any uploaded data under `backend/var/`.
- Generated reports (may contain customer/site identifiers).

Expanded `.gitignore` (to be added at repo root):

```
# Secrets & env
.env
.env.*
!.env.example

# OS / editor
.DS_Store
Thumbs.db
.idea/
.vscode/

# Python
__pycache__/
*.py[cod]
*.egg-info/
.venv/
venv/
.pytest_cache/
.ruff_cache/
.mypy_cache/
.coverage
htmlcov/
dist/
build/

# Project data & runtime artifacts (PUBLIC REPO — DO NOT COMMIT)
/data/
/backend/var/
/backend/.venv/
*.log
```

Belt-and-braces:

- `pre-commit` hook with `detect-secrets` to block accidental key commits.
- `Settings` rejects empty/placeholder values at startup so the app fails loudly rather than silently making unauthenticated calls.
- README will state explicitly: never paste real keys into issues/PRs/commits.

## 6. API surface (initial)

- `GET /health`
- `GET /templates` — list available report templates
- `POST /inspections` — multipart upload → returns `inspection_id`
- `POST /inspections/{id}/run` — kick off pipeline (or auto-run on upload)
- `GET /inspections/{id}` — status + intermediate artifacts (transcript, findings)
- `GET /inspections/{id}/report` — streams the generated `.xlsx`

## 7. Tests — placeholder only

For prototype speed:

- `tests/` exists with a `.gitkeep` and nothing else (or a single `test_smoke.py` with a `pass` test so `pytest` runs green).
- `pyproject.toml` declares `pytest` as a dev dep so the team can fill them in later without re-tooling.
- No CI test job wired up yet.

## 8. Production-ready hygiene (still applies)

- **Linters/formatters**: `ruff` (lint + format), `mypy` on `app/`.
- **Pre-commit**: ruff, mypy, end-of-file-fixer, check-yaml, **detect-secrets**.
- **Resilience**: `tenacity` retry (exponential backoff) on 429/5xx; per-request timeouts; concurrency cap.
- **Observability**: structlog JSON logs with `inspection_id` correlation; FastAPI exception handlers returning typed error envelopes (no secret leakage).
- **Docker**: slim Python image, non-root user, healthcheck on `/health`.

## 9. Open decisions (need your call before coding)

1. **Sync vs background** — return report inline (blocks ~30–120s for many images) or background job + polling? Default recommendation: background + `GET /status`.
2. **xlsx output style** — (a) generate a fresh workbook from LLM JSON (simpler, no template formatting preserved), or (b) clone the chosen template `.xlsx` and have the LLM emit cell-address → value mappings to overwrite it (preserves layout/formatting, more brittle). Default recommendation: (a) for prototype.
3. **Language** — transcribe in source language and translate to English for the report, or keep source language end-to-end?

## 10. Build order (once approved)

1. Scaffold `pyproject.toml` (uv), `ruff`/`mypy` config, pre-commit (with detect-secrets), Makefile, expanded `.gitignore`, new `.env.example`.
2. FastAPI app skeleton + `/health` + structured logging + Pydantic Settings (with strict key validation).
3. Storage abstraction + local-fs impl under `backend/var/` (gitignored).
4. Domain models (Pydantic).
5. Two clients: OpenAI (Whisper) + Azure OpenAI (GPT).
6. Whisper transcription service.
7. EXIF + correlation service (using real demo images).
8. Vision service (single-image findings via Azure GPT).
9. Template loader (xlsx → text context) + report builder + xlsx writer; end-to-end smoke against demo data.
10. Dockerfile + minimal README run instructions.
