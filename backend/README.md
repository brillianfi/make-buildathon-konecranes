# Drone Inspection Backend

Backend that turns drone inspection data (images + a single operator audio track) into a structured `.xlsx` report. Whisper handles transcription. Azure-hosted GPT handles per-image vision analysis and report synthesis.

Both models are Azure AI Foundry deployments. Whisper and GPT are configured separately (independent endpoint, api-version, deployment) but share one API key.

---

## Quick start

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
cp ../.env.example ../.env     # then fill in real values (DO NOT COMMIT)
make install                   # uv sync
make dev                       # http://localhost:8000  · docs at /docs
```

OpenAPI / Swagger UI: <http://localhost:8000/docs>

---

## Environment variables

All read from `../.env` at the repo root (or `./backend/.env`). The app fails to start if any of the marked-required keys are empty.

| Variable | Required | Purpose |
|---|---|---|
| `AZURE_OPENAI_API_KEY` | ✅ | Shared Azure key for both deployments. |
| `AZURE_OPENAI_WHISPER_ENDPOINT` | ✅ | e.g. `https://<resource>.cognitiveservices.azure.com` |
| `AZURE_OPENAI_WHISPER_API_VERSION` | optional | default `2024-06-01` |
| `AZURE_OPENAI_WHISPER_DEPLOYMENT` | ✅ | the deployment **name** in Foundry (not the model name) |
| `AZURE_OPENAI_GPT_ENDPOINT` | ✅ | e.g. `https://<resource>.cognitiveservices.azure.com` |
| `AZURE_OPENAI_GPT_API_VERSION` | optional | default `2024-12-01-preview` |
| `AZURE_OPENAI_GPT_DEPLOYMENT` | ✅ | deployment name (e.g. `gpt-5.4`) |
| `LOG_LEVEL` | optional | `INFO` (default) |
| `STORAGE_DIR` | optional | runtime artifacts root, default `./var` |
| `TEMPLATES_DIR` | optional | xlsx templates folder, default `../data/4 Report Templates` |
| `GLOSSARY_PATH` | optional | path to a text glossary; PDFs are skipped |
| `MAX_UPLOAD_MB` | optional | default `200` |
| `CORS_ORIGINS` | optional | comma-separated allowlist for the frontend |

---

## Endpoints

Base URL: `http://localhost:8000`

### `GET /health`

Liveness probe. No auth.

**Response 200**
```json
{"status": "ok"}
```

### `GET /templates`

List `.xlsx` templates available in `TEMPLATES_DIR`. The `filename` value is what you pass to `POST /inspections`.

**Response 200**
```json
[
  {
    "filename": "Inspection_Report.xlsx",
    "path": "/abs/path/to/data/4 Report Templates/Inspection_Report.xlsx",
    "size_bytes": 24576
  }
]
```

### `POST /inspections`

Create an inspection. Uploads images + a single audio file + a metadata manifest. Returns a Pydantic `Inspection` model with status `created`. **No model calls happen here** — call `/run` to execute the pipeline.

**Request — `multipart/form-data`**

| Field | Type | Required | Notes |
|---|---|---|---|
| `metadata` | text (JSON) | ✅ | JSON array, one entry per uploaded image: `[{"filename": "...", "captured_at": "<ISO datetime>", "location": "..."}]`. `filename` must match the upload. `location` is optional. |
| `images` | file (×N) | ✅ | `.jpg/.jpeg/.png/.webp` |
| `audio` | file (×1) | ✅ | one file. `.m4a/.mp3/.wav/.ogg/.flac/.webm` |
| `template_filename` | text | optional | filename of an `.xlsx` from `GET /templates`. If omitted, the LLM designs a sensible default workbook (one "Inspection" sheet per finding + a "Summary" sheet). |
| `audio_started_at` | text (ISO datetime) | optional | wall-clock time when the audio recording began. Defaults to the earliest image's `captured_at`. Used to align audio segments with images. |
| `audio_language` | text | optional | ISO 639-1 (`"en"`, `"fi"`, …) or `"auto"`. Default `"auto"`. **Recommended:** set explicitly — Whisper auto-detection has misclassified accented English as Finnish on this corpus. |

**Response 201**
```json
{
  "id": "8e0a...",
  "template_filename": "Inspection_Report.xlsx",
  "status": "created",
  "images": [...],
  "audio": {"filename": "operator.m4a", "path": "..."},
  "audio_started_at": null,
  "audio_language": "en",
  "transcript": null,
  "findings": [],
  "report_path": null,
  "error": null
}
```

**Errors**
- `400 validation_error` — bad metadata JSON, missing metadata for an image, unsupported file type, missing template.
- `400 validation_error` — when at least one image or the audio is missing.

### `POST /inspections/{id}/run`

Run the pipeline (transcribe → correlate → vision → synthesise → write xlsx).

**Query params**
- `sync` — `true` blocks until the pipeline finishes (good for scripted/CLI use). `false` (default) returns immediately and runs in a background task; poll `GET /inspections/{id}` to track status.

**Response 200** — same `Inspection` shape. With `sync=true`, status will be `completed` or `failed`. With async, status is `running` and the body fills in over time.

### `GET /inspections/{id}`

Get the current state of an inspection (status, transcript, findings, error).

**Response 200** — `Inspection` model.

`status` lifecycle: `created` → `running` → `completed` | `failed`.

### `GET /inspections/{id}/report`

Stream the generated `.xlsx`. Only available when `status == completed`.

**Response 200** — binary `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` with `Content-Disposition: attachment; filename="inspection-<id>.xlsx"`.

**Errors**
- `404 not_found` — unknown inspection id.
- `400 validation_error` — report not ready yet (status `created`/`running`/`failed`).

---

## End-to-end example (curl)

```bash
# 1. List templates
curl http://localhost:8000/templates

# 2. Create the inspection (template_filename is optional)
curl -X POST http://localhost:8000/inspections \
  -F "template_filename=Inspection_Report.xlsx" \  # optional — omit to use default layout
  -F 'metadata=[
        {"filename":"DJI_001.JPG","captured_at":"2026-03-17T15:49:03Z","location":"Hall A, Bay 2"},
        {"filename":"DJI_002.JPG","captured_at":"2026-03-17T15:49:42Z","location":"Hall A, Bay 3"}
      ]' \
  -F "images=@DJI_001.JPG" \
  -F "images=@DJI_002.JPG" \
  -F "audio=@operator.m4a" \
  -F "audio_language=en"
# → {"id": "8e0a...", "status": "created", ...}

# 3. Run the pipeline (sync — blocks ~30–120s)
curl -X POST "http://localhost:8000/inspections/8e0a.../run?sync=true"

# Or async + poll:
curl -X POST "http://localhost:8000/inspections/8e0a.../run"
curl http://localhost:8000/inspections/8e0a...   # poll until status=="completed"

# 4. Download the .xlsx
curl -OJ http://localhost:8000/inspections/8e0a.../report
```

---

## Pipeline (what `/run` does)

1. **Transcribe** the single audio file with Whisper (`response_format=verbose_json`, per-segment timestamps). Glossary text — if any — is passed as a Whisper prompt for terminology bias. `audio_language` forces detection when not `"auto"`.
2. **Sort images** by frontend-supplied `captured_at`.
3. **Anchor audio** at `audio_started_at` (or earliest image's `captured_at`).
4. **Correlate** each image with overlapping transcript segments (±5 s window).
5. **Vision pass** — for every image, call GPT with `(image, operator_commentary, location, glossary_excerpt)` and a JSON-schema `response_format`. Parallelised at 4 workers. Returns one structured `Finding{component, condition, severity, observation, recommendation}` per image.
6. **Template flatten** — read the chosen `.xlsx` with openpyxl and dump cells as text.
7. **Synthesis** — call GPT with `findings + per-image metadata + transcript + glossary + template-as-text`, structured-output JSON describing the workbook to write.
8. **Write `.xlsx`** with openpyxl to `STORAGE_DIR/inspections/<id>/report.xlsx`.

State is held in an in-memory dict; restart loses inspection metadata, but on-disk uploads + reports under `STORAGE_DIR` persist.

---

## Layout

```
backend/
├── app/
│   ├── api/                # FastAPI routers
│   │   ├── health.py
│   │   ├── inspections.py  # POST upload · POST run · GET status · GET report
│   │   └── templates.py
│   ├── clients/
│   │   └── azure_openai.py # get_whisper_client(), get_gpt_client()
│   ├── core/
│   │   ├── config.py       # Pydantic Settings, fails on empty required keys
│   │   ├── errors.py
│   │   ├── logging.py      # structlog JSON
│   │   └── prompts.py      # load_prompt("vision.system" / "report.system")
│   ├── domain/             # Pydantic models (Inspection, Finding, …)
│   ├── prompts/            # markdown prompt files
│   │   ├── vision.system.md
│   │   └── report.system.md
│   ├── services/           # business logic — no FastAPI imports
│   │   ├── transcription.py
│   │   ├── correlation.py
│   │   ├── vision.py
│   │   ├── template_loader.py
│   │   ├── report_builder.py
│   │   ├── xlsx_writer.py
│   │   ├── glossary.py
│   │   └── pipeline.py     # orchestrates a single /run
│   ├── storage/
│   │   ├── base.py         # Storage Protocol
│   │   └── local.py        # filesystem impl
│   └── main.py             # FastAPI app factory
├── scripts/
│   ├── smoke_all.py        # exercises Whisper + GPT text + GPT vision/JSON
│   ├── smoke_azure.py      # Whisper + GPT summary on a demo audio file
│   └── smoke_gpt.py        # GPT-only roundtrip
├── tests/test_smoke.py     # placeholder (pytest passes; no real coverage)
├── pyproject.toml          # uv-managed
└── Dockerfile
```

Runtime artifacts live in `STORAGE_DIR` (default `backend/var/`). Layout per inspection: `inspections/<uuid>/{images/, audio/, report.xlsx}`. Gitignored.

---

## Smoke scripts

Run from the `backend/` directory after `make install` and a populated `.env`:

```bash
PYTHONPATH=. uv run python scripts/smoke_all.py    # all four checks
PYTHONPATH=. uv run python scripts/smoke_azure.py  # Whisper + GPT summary
PYTHONPATH=. uv run python scripts/smoke_gpt.py    # GPT only
```

`smoke_all.py` exercises:
1. Settings load + endpoints visible
2. `transcribe()` against the small Finnish demo audio
3. GPT plain-text round-trip
4. `analyse_image()` with vision + JSON-schema response on a demo JPG

If all four pass, both deployments are healthy and the full pipeline will work.

---

## Quality gates

```bash
make lint        # ruff check + ruff format --check
make typecheck   # mypy --strict (29 source files)
make check       # both
```

Tests are placeholders only (`tests/test_smoke.py` with `assert True`). No real coverage by design — this is a buildathon prototype.

---

## Notes for callers

- `POST /inspections` does not run any model — it only persists files. Always follow with `POST /inspections/{id}/run`.
- `audio_language` is recommended; auto-detection is unreliable on accented English.
- Filenames in `metadata[].filename` **must** match the multipart `images` filenames byte-for-byte.
- Cell values in the synthesised xlsx are constrained to scalars (`string | number | boolean | null`).
- `gpt-5.4` is a reasoning model: it rejects `temperature` and `max_tokens`. Service code uses `max_completion_tokens` where caps are needed.

---

## Public-repo safety

This repo is public. Never commit:
- `.env` with real keys
- Anything under `data/` or `backend/var/`
- Generated reports

Keys are only ever read from `.env` via `pydantic-settings` — never hardcode them. `.gitignore` enforces the file-level rules.
