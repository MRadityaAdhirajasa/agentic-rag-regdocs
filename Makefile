.PHONY: up down logs smoke check ingest ingest-reset chat lint fmt test all


up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f qdrant

smoke:
	uv run python scripts/smoke_qdrant.py seed

check:
	uv run python scripts/smoke_qdrant.py check

ingest:
	uv run python -m scripts.ingest

ingest-reset:
	uv run python -m scripts.ingest --reset

chat:
	uv run python -m scripts.chat

lint:
	uv run ruff check .
	uv run mypy app scripts

fmt:
	uv run ruff format .
	uv run ruff check --fix .

test:
	uv run pytest

all: lint test