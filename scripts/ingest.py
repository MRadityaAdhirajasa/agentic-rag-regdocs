"""Masukkan kedua jenis sumber ke satu collection Qdrant.

    uv run python -m scripts.ingest              # regulasi + FAQ
    uv run python -m scripts.ingest --faq        # FAQ saja
    uv run python -m scripts.ingest --pdf        # regulasi saja
    uv run python -m scripts.ingest --reset      # hapus collection dulu
    uv run python -m scripts.ingest --doc uu-6-2023   # satu dokumen saja

Ingest ulang aman: id titik diturunkan dari chunk_id, jadi yang lama ditimpa,
bukan digandakan.

Dibedakan lewat payload `source_type`, bukan lewat collection terpisah —
itu yang bikin filter dan perbandingan antar sumber mungkin nanti.
"""

import sys

from app.core.config import QDRANT_COLLECTION
from app.core.embeddings import embed
from app.ingestion import faq, pdf, store


def main(argv: list[str]) -> None:
    reset = "--reset" in argv
    hanya_faq = "--faq" in argv
    hanya_pdf = "--pdf" in argv

    doc_ids = [argv[i + 1] for i, a in enumerate(argv) if a == "--doc"]
    if doc_ids:
        hanya_pdf = True

    records = []
    if not hanya_faq:
        print("Regulasi:")
        records += pdf.all_records(doc_ids or None)
    if not hanya_pdf:
        print("FAQ:")
        records += faq.records()

    print(f"\nTotal {len(records)} chunk untuk di-embed.")
    client = store.connect()

    # Satu chunk di-embed duluan hanya untuk mengukur dimensi, lalu collection
    # divalidasi. Kalau dimensinya bentrok, kita berhenti setelah 1 request —
    # bukan setelah membakar seluruh kuota harian.
    probe = embed([records[0]["text"]], kind="document")
    store.ensure_collection(client, len(probe[0]), reset)

    vectors = probe + embed([r["text"] for r in records[1:]], kind="document")
    print(f"{len(vectors)} vektor, dimensi {len(vectors[0])}.")

    store.upsert(client, records, vectors)

    total = client.count(collection_name=QDRANT_COLLECTION).count
    print(f"Selesai. Total titik di '{QDRANT_COLLECTION}': {total}")


if __name__ == "__main__":
    main(sys.argv[1:])
