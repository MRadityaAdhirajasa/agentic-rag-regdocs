"""Dense-only search, k=3. Sengaja sesederhana ini.

Hybrid (sparse + RRF) baru masuk Tahap 6, reranking Tahap 7. Fungsi ini yang
akan diukur `make eval` di Tahap 4, jadi bentuknya dipisah dari CLI sejak awal.
"""

from qdrant_client import QdrantClient
from qdrant_client.models import ScoredPoint

from app.core.config import QDRANT_COLLECTION, QDRANT_URL
from app.core.embeddings import embed

TOP_K = 3


def search(query: str, limit: int = TOP_K) -> list[ScoredPoint]:
    vector = embed([query], kind="query")[0]
    client = QdrantClient(url=QDRANT_URL)
    return client.query_points(
        collection_name=QDRANT_COLLECTION,
        query=vector,
        limit=limit,
        with_payload=True,
    ).points
