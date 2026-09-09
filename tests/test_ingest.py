"""Test tanpa jaringan: yang diuji cuma logika pemotongan teks.

Embedding dan Qdrant sengaja tidak disentuh — CI tidak punya API key maupun
container, dan test yang butuh keduanya akan jadi test yang selalu dimatikan.
"""

from app.ingestion.ingest_pdf import CHUNK_SIZE, split


def test_split_menghasilkan_chunk() -> None:
    teks = "Pasal 1. Ketentuan umum. " * 200
    chunks = split(teks)
    assert len(chunks) > 1
    assert all(len(c) <= CHUNK_SIZE for c in chunks)


def test_split_membuang_yang_kosong() -> None:
    assert split("   \n\n   ") == []
