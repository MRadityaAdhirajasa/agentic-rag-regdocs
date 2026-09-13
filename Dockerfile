# Container untuk API. Qdrant tetap pakai image resminya sendiri.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.9.9 /uv /bin/uv

WORKDIR /app

# Dependensi dipasang sebelum kode disalin, supaya lapisan ini tetap
# terpakai ulang selama pyproject/uv.lock tidak berubah.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY app/ ./app/
COPY data/metadata.csv ./data/metadata.csv
COPY dokumen/faq/ ./dokumen/faq/

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    # model fastembed (BM25 + reranker 1,1 GB) diarahkan ke volume,
    # supaya tidak diunduh ulang tiap container dibuat
    FASTEMBED_CACHE_PATH=/app/.cache/fastembed \
    EMBED_CACHE_PATH=/app/.cache/embed_cache.sqlite

EXPOSE 8000
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
