"""Sisi sparse: BM25, dihitung di komputer sendiri tanpa memanggil API.

Kenapa BM25 dan bukan SPLADE atau miniCOIL: keduanya hanya untuk bahasa
Inggris. BM25 tidak bergantung bahasa karena dia mencocokkan kata apa adanya.

Kenapa stemming dimatikan: Bahasa Indonesia tidak ada di daftar bahasa yang
didukung — bukan kekurangan fastembed, tapi py-rust-stemmers sendiri memang
tidak punya stemmer Indonesia. Akibatnya "perizinan" dan "izin" dianggap kata
berbeda.

Itu kehilangan yang bisa diterima, karena tugas sisi sparse di sini bukan
memahami makna — itu tugas sisi dense. Tugasnya mencocokkan penanda yang
harus persis: "Pasal 227", "NIB", "PB UMKU", "KBLI 47111". Justru di situ
sisi dense sering meleset.

Bobot IDF tidak dihitung di sini, melainkan oleh Qdrant lewat
`Modifier.IDF` — supaya dasar hitungnya seluruh korpus, bukan per batch.
"""

from functools import lru_cache

from fastembed import SparseTextEmbedding
from qdrant_client.models import SparseVector

MODEL = "Qdrant/bm25"


@lru_cache(maxsize=1)
def _model() -> SparseTextEmbedding:
    # dimuat sekali dan ditahan: memuat ulang per panggilan itu boros
    return SparseTextEmbedding(MODEL, disable_stemmer=True)


def _ke_sparse(v: object) -> SparseVector:
    return SparseVector(indices=v.indices.tolist(), values=v.values.tolist())  # type: ignore[attr-defined]


def encode_dokumen(texts: list[str]) -> list[SparseVector]:
    return [_ke_sparse(v) for v in _model().embed(texts)]


def encode_query(texts: list[str]) -> list[SparseVector]:
    """Sisi query tidak diberi bobot frekuensi — Qdrant yang menimbang lewat IDF."""
    return [_ke_sparse(v) for v in _model().query_embed(texts)]
