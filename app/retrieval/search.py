"""Dense-only search, k=3, dengan filter opsional per jenis sumber.

Filter `source_type` adalah buah dari keputusan Tahap 2 menaruh regulasi dan
FAQ di satu collection: memisahkan keduanya cukup satu argumen, dan
membandingkan keduanya jadi mungkin. Routing otomatis baru di Tahap 9.

Hybrid (sparse + RRF) baru masuk Tahap 6, reranking Tahap 7. Fungsi ini yang
akan diukur `make eval` di Tahap 4, jadi bentuknya dipisah dari CLI sejak awal.
"""

from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue, ScoredPoint

from app.core.config import QDRANT_COLLECTION, QDRANT_URL
from app.core.embeddings import embed

TOP_K = 3


def search(query: str, limit: int = TOP_K, source_type: str | None = None) -> list[ScoredPoint]:
    vector = embed([query], kind="query")[0]
    client = QdrantClient(url=QDRANT_URL)
    kondisi = (
        Filter(must=[FieldCondition(key="source_type", match=MatchValue(value=source_type))])
        if source_type
        else None
    )
    return client.query_points(
        collection_name=QDRANT_COLLECTION,
        query=vector,
        limit=limit,
        query_filter=kondisi,
        with_payload=True,
    ).points
