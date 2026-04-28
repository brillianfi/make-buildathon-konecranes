.PHONY: help install dev fmt lint typecheck check run clean

help:
	@echo "install   - install dependencies via uv"
	@echo "dev       - run uvicorn with reload"
	@echo "run       - run uvicorn (production-style)"
	@echo "fmt       - format with ruff"
	@echo "lint      - lint with ruff"
	@echo "typecheck - run mypy"
	@echo "check     - fmt + lint + typecheck"
	@echo "clean     - remove caches"

install:
	uv sync

dev:
	uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

run:
	uv run uvicorn app.main:app --host 0.0.0.0 --port 8000

fmt:
	uv run ruff format .
	uv run ruff check --fix .

lint:
	uv run ruff check .
	uv run ruff format --check .

typecheck:
	uv run mypy

check: lint typecheck

clean:
	rm -rf .ruff_cache .mypy_cache .pytest_cache __pycache__ .venv
	find . -type d -name __pycache__ -exec rm -rf {} +
