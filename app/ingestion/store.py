"""Bagian Qdrant yang dipakai bareng oleh loader PDF maupun FAQ.

Dipisah supaya kedua loader tidak menyalin logika yang sama: pembuatan
collection, penjagaan dimensi, dan pemecahan upsert.
"""

import uuid
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from app.core.config import QDRANT_COLLECTION, QDRANT_URL

# Qdrant menolak body HTTP di atas 32 MB. Vektor 2048 dimensi cepat sekali
# menembusnya, jadi upsert selalu dipecah.
UPSERT_BATCH = 256

NAMESPACE = uuid.UUID("00000000-0000-0000-0000-000000000001")


def connect() -> QdrantClient:
    return QdrantClient(url=QDRANT_URL)


def ensure_collection(client: QdrantClient, size: int, reset: bool = False) -> None:
    """Bikin collection kalau belum ada; tolak keras kalau dimensinya beda.

    Dimensi collection tidak bisa diubah setelah dibuat. Tanpa penjagaan ini,
    yang gagal adalah upsert-nya, dengan pesan yang jauh lebih membingungkan.
    """
    existing = {c.name for c in client.get_collections().collections}

    if reset and QDRANT_COLLECTION in existing:
        client.delete_collection(QDRANT_COLLECTION)
        existing.discard(QDRANT_COLLECTION)
        print(f"Collection '{QDRANT_COLLECTION}' dihapus (--reset).")

    if QDRANT_COLLECTION not in existing:
        client.create_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=VectorParams(size=size, distance=Distance.COSINE),
        )
        print(f"Collection '{QDRANT_COLLECTION}' dibuat, dimensi {size}.")
        return

    current = client.get_collection(QDRANT_COLLECTION).config.params.vectors
    if not isinstance(current, VectorParams):
        # named vectors baru dipakai mulai Tahap 6 (hybrid search)
        raise SystemExit(f"Collection '{QDRANT_COLLECTION}' pakai named vectors, bukan tunggal.")
    if current.size != size:
        raise SystemExit(
            f"Collection '{QDRANT_COLLECTION}' berdimensi {current.size}, "
            f"model embedding menghasilkan {size}.\n"
            f"Dimensi collection tidak bisa diubah. Jalankan ulang dengan --reset."
        )


def upsert(client: QdrantClient, records: list[dict[str, Any]], vectors: list[list[float]]) -> None:
    points = [
        PointStruct(
            # id deterministik dari chunk_id: ingest ulang menimpa, bukan menggandakan
            id=str(uuid.uuid5(NAMESPACE, r["payload"]["chunk_id"])),
            vector=vector,
            payload=r["payload"],
        )
        for r, vector in zip(records, vectors, strict=True)
    ]
    for start in range(0, len(points), UPSERT_BATCH):
        client.upsert(
            collection_name=QDRANT_COLLECTION,
            points=points[start : start + UPSERT_BATCH],
        )
        print(f"  upsert {min(start + UPSERT_BATCH, len(points))}/{len(points)}")
