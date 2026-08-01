.PHONY: install format lint typecheck test schema schema-check check scan

install:
	uv sync --all-groups

format:
	uv run ruff format .
	uv run ruff check --fix .

lint:
	uv run ruff format --check .
	uv run ruff check .

typecheck:
	uv run mypy src tests

test:
	uv run pytest

schema:
	uv run python scripts/export_schema.py

schema-check:
	uv run python scripts/export_schema.py --check

check: lint typecheck schema-check test

scan:
	uv run web-openness scan example.org
