"""Smoke test Qdrant: bikin collection, isi satu titik, hitung ulang.

Pakai:
    uv run python scripts/smoke_qdrant.py seed
    uv run python scripts/smoke_qdrant.py check
"""

import os
import sys

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION = os.getenv("QDRANT_COLLECTION", "regdocs")
VECTOR_SIZE = 768  # sesuaikan dengan model embedding nanti


def get_client() -> QdrantClient:
    return QdrantClient(url=QDRANT_URL)


def seed() -> None:
    client = get_client()

    existing = {c.name for c in client.get_collections().collections}
    if COLLECTION not in existing:
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )
        print(f"Collection '{COLLECTION}' dibuat.")
    else:
        print(f"Collection '{COLLECTION}' sudah ada.")

    client.upsert(
        collection_name=COLLECTION,
        points=[
            PointStruct(
                id=1,
                vector=[0.1] * VECTOR_SIZE,
                payload={
                    "source_type": "dummy",
                    "text": "titik uji coba tahap 0",
                },
            )
        ],
    )
    print("1 titik dimasukkan.")
    check()


def check() -> None:
    client = get_client()

    existing = {c.name for c in client.get_collections().collections}
    if COLLECTION not in existing:
        print(f"GAGAL: collection '{COLLECTION}' tidak ditemukan.")
        sys.exit(1)

    total = client.count(collection_name=COLLECTION).count
    print(f"Jumlah titik di '{COLLECTION}': {total}")

    if total == 0:
        print("GAGAL: collection kosong. Volume kemungkinan tidak persist.")
        sys.exit(1)

    # Dimensi dibaca dari collection, bukan ditebak. Sejak Tahap 1 isinya
    # vektor 2048 dari nemotron, bukan lagi dummy 768.
    params = client.get_collection(COLLECTION).config.params.vectors
    size = params.size if isinstance(params, VectorParams) else VECTOR_SIZE
    hits = client.query_points(
        collection_name=COLLECTION,
        query=[0.1] * size,
        limit=1,
    )
    print(f"Hasil pencarian: {hits.points}")
    print("OK.")


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "check"
    if command == "seed":
        seed()
    elif command == "check":
        check()
    else:
        print("Perintah: seed | check")
        sys.exit(1)
