.PHONY: up down logs smoke check lint fmt test all

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

lint:
	uv run ruff check .
	uv run mypy app scripts

fmt:
	uv run ruff format .
	uv run ruff check --fix .

test:
	uv run pytest

all: lint test