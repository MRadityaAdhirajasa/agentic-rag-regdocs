from functools import lru_cache

from fastembed import SparseTextEmbedding
from qdrant_client.models import SparseVector

MODEL = "Qdrant/bm25"


@lru_cache(maxsize=1)
def _model() -> SparseTextEmbedding:
    # Stemming dimatikan karena py-rust-stemmers tidak punya stemmer Bahasa Indonesia.
    return SparseTextEmbedding(MODEL, disable_stemmer=True)


def _ke_sparse(v: object) -> SparseVector:
    return SparseVector(indices=v.indices.tolist(), values=v.values.tolist())  # type: ignore[attr-defined]


def encode_dokumen(texts: list[str]) -> list[SparseVector]:
    return [_ke_sparse(v) for v in _model().embed(texts)]


def encode_query(texts: list[str]) -> list[SparseVector]:
    return [_ke_sparse(v) for v in _model().query_embed(texts)]
