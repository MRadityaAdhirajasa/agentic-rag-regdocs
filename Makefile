.PHONY: up down logs smoke check ingest chat lint fmt test all

PDF ?= dokumen/PDF/Peraturan Menteri Investasi dan Hilirisasi Kepala Badan Koordinasi Penanaman Modal Nomor 5 Tahun 2025.pdf

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
	uv run python -m app.ingestion.ingest_pdf "$(PDF)"

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