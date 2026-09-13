"""Penyusun ulang hasil dengan cross-encoder. Jalan lokal di CPU, tanpa API.

Bedanya dengan pencarian biasa: pencarian membandingkan **dua vektor yang
dihitung terpisah**, jadi pertanyaan dan dokumen tidak pernah benar-benar
saling melihat. Cross-encoder membaca keduanya sekaligus dalam satu jalan,
sehingga bisa menangkap hubungan yang hilang saat keduanya diringkas jadi
vektor. Ongkosnya: tidak bisa dihitung di muka, harus dijalankan saat
pertanyaan datang — karena itu hanya dipakai untuk 20 kandidat teratas,
bukan seluruh korpus.

Roadmap meminta `BAAI/bge-reranker-v2-m3`. Model itu tidak tersedia lewat
fastembed, dan memasangnya berarti menambah PyTorch (~2 GB) untuk satu
fungsi. Yang dipakai `jinaai/jina-reranker-v2-base-multilingual`: sama-sama
multilingual, jalan di ONNX, dan fastembed sudah terpasang sejak Tahap 6.
`BAAI/bge-reranker-base` yang juga tersedia sengaja dilewati — dia dilatih
untuk Mandarin dan Inggris, bukan multilingual.

Skornya logit, bukan 0-1, dan **wajar bernilai negatif**. Yang berarti
selisih antar kandidat, bukan nilai mutlaknya.
"""

from functools import lru_cache

from fastembed.rerank.cross_encoder import TextCrossEncoder
from qdrant_client.models import ScoredPoint

MODEL = "jinaai/jina-reranker-v2-base-multilingual"


@lru_cache(maxsize=1)
def _model() -> TextCrossEncoder:
    # dimuat sekali lalu ditahan: model 1,1 GB, memuat ulang per pertanyaan itu fatal
    return TextCrossEncoder(MODEL)


def rerank(query: str, hits: list[ScoredPoint], limit: int) -> list[ScoredPoint]:
    """Susun ulang `hits` menurut cross-encoder, kembalikan `limit` teratas."""
    if len(hits) <= 1:
        return hits[:limit]

    teks = [str(h.payload["text"]) if h.payload else "" for h in hits]
    skor = list(_model().rerank(query, teks))

    urut = sorted(zip(skor, hits, strict=True), key=lambda x: x[0], reverse=True)
    keluar = []
    for nilai, h in urut[:limit]:
        # skor lama ditimpa supaya yang terlihat di sitasi adalah dasar
        # urutan yang sebenarnya dipakai, bukan skor pencarian yang sudah usang
        h.score = float(nilai)
        keluar.append(h)
    return keluar
