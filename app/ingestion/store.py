"""Bagian Qdrant yang dipakai bareng oleh loader PDF maupun FAQ.

Sejak Tahap 6 satu titik membawa **dua vektor bernama**: `dense` dari model
embedding, dan `sparse` dari BM25. Keduanya di collection yang sama supaya
Qdrant bisa menggabungkan hasil keduanya sendiri lewat RRF, tanpa kita
menyatukan dua daftar hasil secara manual di Python.

Indeks sparse dipasangi `Modifier.IDF`: bobot kata langka dihitung Qdrant
berdasarkan seluruh korpus. Kalau dihitung di sisi kita, dasarnya cuma batch
yang sedang diproses, dan bobotnya jadi salah.
"""

import uuid
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    Modifier,
    PointStruct,
    SparseIndexParams,
    SparseVector,
    SparseVectorParams,
    VectorParams,
)

from app.core.config import QDRANT_COLLECTION, QDRANT_URL

# Qdrant menolak body HTTP di atas 32 MB. Vektor 2048 dimensi cepat sekali
# menembusnya, jadi upsert selalu dipecah.
UPSERT_BATCH = 256

NAMA_DENSE = "dense"
NAMA_SPARSE = "sparse"
NAMESPACE = uuid.UUID("00000000-0000-0000-0000-000000000001")


def connect() -> QdrantClient:
    return QdrantClient(url=QDRANT_URL)


def ensure_collection(client: QdrantClient, size: int | None, reset: bool = False) -> None:
    """Bikin collection kalau belum ada; tolak keras kalau bentuknya tidak cocok.

    Dimensi maupun susunan vektor tidak bisa diubah setelah collection dibuat.
    Tanpa penjagaan ini, yang gagal adalah upsert-nya, dengan pesan yang jauh
    lebih membingungkan.

    `size=None` membuat collection **sparse saja** — dipakai gate CI, yang
    tidak punya API key maupun kuota untuk menghitung vektor dense.
    """
    existing = {c.name for c in client.get_collections().collections}

    if reset and QDRANT_COLLECTION in existing:
        client.delete_collection(QDRANT_COLLECTION)
        existing.discard(QDRANT_COLLECTION)
        print(f"Collection '{QDRANT_COLLECTION}' dihapus (--reset).")

    if QDRANT_COLLECTION not in existing:
        dense_config = (
            {NAMA_DENSE: VectorParams(size=size, distance=Distance.COSINE)} if size else {}
        )
        client.create_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=dense_config,
            sparse_vectors_config={
                NAMA_SPARSE: SparseVectorParams(index=SparseIndexParams(), modifier=Modifier.IDF)
            },
        )
        bentuk = f"dense {size} + sparse BM25" if size else "sparse BM25 saja"
        print(f"Collection '{QDRANT_COLLECTION}' dibuat: {bentuk}.")
        return

    current = client.get_collection(QDRANT_COLLECTION).config.params.vectors
    if size is None:
        return
    if not isinstance(current, dict) or NAMA_DENSE not in current:
        raise SystemExit(
            f"Collection '{QDRANT_COLLECTION}' masih berbentuk vektor tunggal (sebelum Tahap 6).\n"
            f"Susunan vektor tidak bisa diubah. Jalankan ulang dengan --reset."
        )
    if current[NAMA_DENSE].size != size:
        raise SystemExit(
            f"Vektor '{NAMA_DENSE}' di collection berdimensi {current[NAMA_DENSE].size}, "
            f"model embedding menghasilkan {size}.\n"
            f"Dimensi tidak bisa diubah. Jalankan ulang dengan --reset."
        )


def upsert(
    client: QdrantClient,
    records: list[dict[str, Any]],
    vectors: list[list[float]] | None,
    sparse: list[SparseVector],
) -> None:
    dense_list: list[list[float] | None] = (
        list(vectors) if vectors is not None else [None] * len(records)
    )
    points = []
    for r, dense, jarang in zip(records, dense_list, sparse, strict=True):
        isi: dict[str, Any] = {NAMA_SPARSE: jarang}
        if dense is not None:
            isi[NAMA_DENSE] = dense
        points.append(
            PointStruct(
                # id deterministik dari chunk_id: ingest ulang menimpa, bukan menggandakan
                id=str(uuid.uuid5(NAMESPACE, r["payload"]["chunk_id"])),
                vector=isi,
                payload=r["payload"],
            )
        )
    for start in range(0, len(points), UPSERT_BATCH):
        client.upsert(
            collection_name=QDRANT_COLLECTION,
            points=points[start : start + UPSERT_BATCH],
        )
        print(f"  upsert {min(start + UPSERT_BATCH, len(points))}/{len(points)}")
