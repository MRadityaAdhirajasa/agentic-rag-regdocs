"""Pencarian hybrid: dense + BM25, digabung Qdrant lewat RRF.

Kenapa RRF dan bukan menjumlahkan skor: skor cosine (0-1) dan skor BM25
(tak terbatas) tidak sebanding, jadi menjumlahkannya butuh normalisasi yang
selalu jadi tebakan. RRF membuang skor sama sekali dan hanya memakai
**peringkat** — dokumen yang muncul tinggi di kedua daftar menang, tanpa
perlu menyetel bobot apa pun.

Penggabungan dilakukan Qdrant, bukan di Python. Bedanya bukan soal rapi:
kalau digabung di sisi kita, dua daftar harus ditarik penuh dulu lewat
jaringan, dan filter `source_type` harus diterapkan dua kali.

`mode` ada supaya eksperimen #2 bisa dijalankan tiga arah tanpa ingest ulang.

Reranking baru masuk Tahap 7.
"""

from qdrant_client import QdrantClient
from qdrant_client.models import (
    FieldCondition,
    Filter,
    Fusion,
    FusionQuery,
    MatchValue,
    Prefetch,
    ScoredPoint,
)

from app.core.config import QDRANT_COLLECTION, QDRANT_URL
from app.core.embeddings import embed
from app.core.sparse import encode_query
from app.ingestion.store import NAMA_DENSE, NAMA_SPARSE

TOP_K = 3
# tiap sisi menyumbang kandidat sebanyak ini sebelum digabung
AMBIL_PER_SISI = 20


def _filter(source_type: str | None) -> Filter | None:
    if not source_type:
        return None
    return Filter(must=[FieldCondition(key="source_type", match=MatchValue(value=source_type))])


def search_many(
    queries: list[str],
    limit: int = TOP_K,
    source_type: str | None = None,
    mode: str = "hybrid",
) -> list[list[ScoredPoint]]:
    """Cari untuk banyak pertanyaan sekaligus.

    Embedding dense-nya satu request untuk semua pertanyaan; sisi sparse
    dihitung lokal.
    """
    if mode not in ("hybrid", "dense", "sparse"):
        raise ValueError(f"mode harus hybrid/dense/sparse, bukan {mode!r}")

    dense = embed(queries, kind="query") if mode in ("hybrid", "dense") else [None] * len(queries)
    jarang = encode_query(queries) if mode in ("hybrid", "sparse") else [None] * len(queries)

    client = QdrantClient(url=QDRANT_URL)
    kondisi = _filter(source_type)
    hasil = []
    for d, s in zip(dense, jarang, strict=True):
        if mode == "dense":
            jawab = client.query_points(
                collection_name=QDRANT_COLLECTION,
                query=d,
                using=NAMA_DENSE,
                limit=limit,
                query_filter=kondisi,
                with_payload=True,
            )
        elif mode == "sparse":
            jawab = client.query_points(
                collection_name=QDRANT_COLLECTION,
                query=s,
                using=NAMA_SPARSE,
                limit=limit,
                query_filter=kondisi,
                with_payload=True,
            )
        else:
            jawab = client.query_points(
                collection_name=QDRANT_COLLECTION,
                prefetch=[
                    Prefetch(query=d, using=NAMA_DENSE, limit=AMBIL_PER_SISI, filter=kondisi),
                    Prefetch(query=s, using=NAMA_SPARSE, limit=AMBIL_PER_SISI, filter=kondisi),
                ],
                query=FusionQuery(fusion=Fusion.RRF),
                limit=limit,
                with_payload=True,
            )
        hasil.append(jawab.points)
    return hasil


def search(
    query: str, limit: int = TOP_K, source_type: str | None = None, mode: str = "hybrid"
) -> list[ScoredPoint]:
    return search_many([query], limit=limit, source_type=source_type, mode=mode)[0]
