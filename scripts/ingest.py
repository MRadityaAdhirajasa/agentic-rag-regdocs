import json
import sys
from pathlib import Path

from app.core.config import QDRANT_COLLECTION
from app.core.embeddings import embed
from app.core.sparse import encode_dokumen
from app.ingestion import faq, pdf, store


def dari_fixture(reset: bool) -> None:
    berkas = Path("eval/korpus_fixture.jsonl")
    if not berkas.exists():
        raise SystemExit(f"{berkas} tidak ada. Jalankan `python -m scripts.buat_fixture` dulu.")
    records = [json.loads(b) for b in berkas.read_text(encoding="utf-8").splitlines() if b.strip()]
    print(f"{len(records)} chunk dari fixture (sparse saja, tanpa API).")

    client = store.connect()
    store.ensure_collection(client, None, reset)
    sparse = encode_dokumen([r["text"] for r in records])
    store.upsert(client, records, None, sparse)
    print(f"Selesai. Total titik di '{QDRANT_COLLECTION}': {client.count(QDRANT_COLLECTION).count}")


def main(argv: list[str]) -> None:
    reset = "--reset" in argv
    if "--fixture" in argv:
        dari_fixture(reset)
        return
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

    probe = embed([records[0]["text"]], kind="document")
    store.ensure_collection(client, len(probe[0]), reset)

    vectors = probe + embed([r["text"] for r in records[1:]], kind="document")
    print(f"{len(vectors)} vektor dense, dimensi {len(vectors[0])}.")

    sparse = encode_dokumen([r["text"] for r in records])
    print(f"{len(sparse)} vektor sparse (BM25, lokal).")

    store.upsert(client, records, vectors, sparse)

    total = client.count(collection_name=QDRANT_COLLECTION).count
    print(f"Selesai. Total titik di '{QDRANT_COLLECTION}': {total}")


if __name__ == "__main__":
    main(sys.argv[1:])
