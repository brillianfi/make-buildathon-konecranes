.PHONY: help install run test fmt lint typecheck check clean

help:
	@echo "install   - install dependencies via uv"
	@echo "run       - launch the desktop app"
	@echo "test      - run pytest"
	@echo "fmt       - format with ruff"
	@echo "lint      - lint with ruff"
	@echo "typecheck - run mypy"
	@echo "check     - lint + typecheck + test"
	@echo "clean     - remove caches and venv"

install:
	uv sync

run:
	uv run python app.py

test:
	uv run pytest

fmt:
	uv run ruff format .
	uv run ruff check --fix .

lint:
	uv run ruff check .
	uv run ruff format --check .

typecheck:
	uv run mypy

check: lint typecheck test

clean:
	rm -rf .venv .ruff_cache .mypy_cache .pytest_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
