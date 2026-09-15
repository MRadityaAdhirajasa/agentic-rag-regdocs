from functools import lru_cache

from fastembed.rerank.cross_encoder import TextCrossEncoder
from qdrant_client.models import ScoredPoint

MODEL = "jinaai/jina-reranker-v2-base-multilingual"


@lru_cache(maxsize=1)
def _model() -> TextCrossEncoder:
    # Model 1,1 GB: tanpa cache ini dia dimuat ulang dari disk tiap pertanyaan.
    return TextCrossEncoder(MODEL)


def rerank(query: str, hits: list[ScoredPoint], limit: int) -> list[ScoredPoint]:
    if len(hits) <= 1:
        return hits[:limit]

    teks = [str(h.payload["text"]) if h.payload else "" for h in hits]
    skor = list(_model().rerank(query, teks))

    urut = sorted(zip(skor, hits, strict=True), key=lambda x: x[0], reverse=True)
    keluar = []
    for nilai, h in urut[:limit]:
        h.score = float(nilai)
        keluar.append(h)
    return keluar
