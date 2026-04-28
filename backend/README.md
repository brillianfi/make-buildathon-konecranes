# Drone Inspection Backend

Backend that converts drone inspection data (images + operator audio) into a structured `.xlsx` report. Whisper handles transcription; an Azure-hosted GPT model handles vision and report synthesis.

## Setup

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
cp ../.env.example ../.env   # then fill in real keys (DO NOT COMMIT)
make install
make dev                     # http://localhost:8000/docs
```

## Layout

```
app/
  api/        FastAPI routers (HTTP boundary)
  core/       config, logging, error handlers
  domain/     Pydantic models
  clients/    OpenAI + Azure OpenAI SDK wrappers
  services/   business logic (transcription, vision, correlation, report build)
  storage/    asset persistence (local-fs by default)
```

Runtime artifacts (uploads, generated reports) live in `backend/var/` and are gitignored.

## Public-repo safety

This repo is public. Never commit:
- `.env` with real keys
- Anything under `data/` or `backend/var/`
- Generated reports

Keys are only ever read from `.env` via `pydantic-settings` — never hardcode them. `.gitignore` enforces the file-level rules.
