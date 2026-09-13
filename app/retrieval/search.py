"""Dense-only search, k=3, dengan filter opsional per jenis sumber.

Filter `source_type` adalah buah dari keputusan Tahap 2 menaruh regulasi dan
FAQ di satu collection: memisahkan keduanya cukup satu argumen, dan
membandingkan keduanya jadi mungkin. Routing otomatis baru di Tahap 9.

`search_many` ada karena evaluasi menanyakan banyak pertanyaan sekaligus.
Satu request embedding menampung 256 teks; menanyakannya satu per satu
berarti 50 request untuk pekerjaan yang muat dalam 1. Selisihnya baru terasa
sakit di Tahap 12, saat evaluasi jalan otomatis di CI yang tidak punya cache.

Hybrid (sparse + RRF) baru masuk Tahap 6, reranking Tahap 7.
"""

from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue, ScoredPoint

from app.core.config import QDRANT_COLLECTION, QDRANT_URL
from app.core.embeddings import embed

TOP_K = 3


def _filter(source_type: str | None) -> Filter | None:
    if not source_type:
        return None
    return Filter(must=[FieldCondition(key="source_type", match=MatchValue(value=source_type))])


def search_many(
    queries: list[str], limit: int = TOP_K, source_type: str | None = None
) -> list[list[ScoredPoint]]:
    """Cari untuk banyak pertanyaan. Embedding-nya satu request untuk semuanya."""
    vectors = embed(queries, kind="query")
    client = QdrantClient(url=QDRANT_URL)
    kondisi = _filter(source_type)
    return [
        client.query_points(
            collection_name=QDRANT_COLLECTION,
            query=vector,
            limit=limit,
            query_filter=kondisi,
            with_payload=True,
        ).points
        for vector in vectors
    ]


def search(query: str, limit: int = TOP_K, source_type: str | None = None) -> list[ScoredPoint]:
    return search_many([query], limit=limit, source_type=source_type)[0]
