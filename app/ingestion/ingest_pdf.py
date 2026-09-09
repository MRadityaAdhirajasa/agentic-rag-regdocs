"""PDF -> chunk -> Qdrant. Versi paling naif yang benar.

Tahap 1 sengaja tidak menyimpan nomor halaman atau nomor pasal — itu jatah
Tahap 2 dan 5. Yang diuji di sini cuma satu hal: apakah pipeline dense-only
kita hidup di Qdrant dan selamat setelah container mati.

Pakai:
    uv run python -m app.ingestion.ingest_pdf "dokumen/PDF/....pdf"
    uv run python -m app.ingestion.ingest_pdf "...pdf" --reset
"""

import sys
import uuid
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from app.core.config import QDRANT_COLLECTION, QDRANT_URL
from app.core.embeddings import embed

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150
NAMESPACE = uuid.UUID("00000000-0000-0000-0000-000000000001")
UPSERT_BATCH = 256


def read_pdf(path: Path) -> str:
    return "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)


def split(text: str) -> list[str]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    return [c for c in splitter.split_text(text) if c.strip()]


def ensure_collection(client: QdrantClient, size: int, reset: bool) -> None:
    """Bikin collection kalau belum ada; tolak keras kalau dimensinya beda.

    Dimensi collection tidak bisa diubah. Kalau tidak dicek di sini, upsert-nya
    yang gagal nanti dengan pesan yang jauh lebih membingungkan.
    """
    existing = {c.name for c in client.get_collections().collections}

    if reset and QDRANT_COLLECTION in existing:
        client.delete_collection(QDRANT_COLLECTION)
        existing.discard(QDRANT_COLLECTION)
        print(f"Collection '{QDRANT_COLLECTION}' dihapus (--reset).")

    if QDRANT_COLLECTION not in existing:
        client.create_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=VectorParams(size=size, distance=Distance.COSINE),
        )
        print(f"Collection '{QDRANT_COLLECTION}' dibuat, dimensi {size}.")
        return

    current = client.get_collection(QDRANT_COLLECTION).config.params.vectors
    if not isinstance(current, VectorParams):
        # named vectors baru dipakai mulai Tahap 6 (hybrid search)
        raise SystemExit(f"Collection '{QDRANT_COLLECTION}' pakai named vectors, bukan tunggal.")
    if current.size != size:
        raise SystemExit(
            f"Collection '{QDRANT_COLLECTION}' berdimensi {current.size}, "
            f"model embedding menghasilkan {size}.\n"
            f"Dimensi collection tidak bisa diubah. Jalankan ulang dengan --reset "
            f"untuk menghapus isinya dan membuat ulang."
        )


def ingest(path: Path, reset: bool = False) -> int:
    chunks = split(read_pdf(path))
    print(f"{path.name}: {len(chunks)} chunk.")

    client = QdrantClient(url=QDRANT_URL)

    # Satu chunk di-embed duluan hanya untuk mengukur dimensi, lalu collection
    # divalidasi. Kalau dimensinya bentrok, kita berhenti setelah 1 request —
    # bukan setelah membakar seluruh kuota harian.
    probe = embed(chunks[:1], kind="document")
    ensure_collection(client, len(probe[0]), reset)

    vectors = probe + embed(chunks[1:], kind="document")
    print(f"{len(vectors)} vektor, dimensi {len(vectors[0])}.")

    doc_id = path.stem
    points = [
        PointStruct(
            # id deterministik: ingest ulang menimpa, bukan menggandakan
            id=str(uuid.uuid5(NAMESPACE, f"{doc_id}:{i}")),
            vector=vector,
            payload={
                "chunk_id": f"{doc_id}:{i}",
                "doc_id": doc_id,
                "source_type": "regulasi",
                "text": chunk,
            },
        )
        for i, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True))
    ]

    # Qdrant menolak body di atas 32 MB. Vektor 2048 dimensi cepat sekali
    # menembusnya, jadi upsert dipecah.
    for start in range(0, len(points), UPSERT_BATCH):
        client.upsert(
            collection_name=QDRANT_COLLECTION, points=points[start : start + UPSERT_BATCH]
        )
        print(f"  upsert {min(start + UPSERT_BATCH, len(points))}/{len(points)}")
    total = client.count(collection_name=QDRANT_COLLECTION).count
    print(f"Masuk. Total titik di '{QDRANT_COLLECTION}': {total}")
    return total


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--reset"]
    if not args:
        raise SystemExit('Pakai: python -m app.ingestion.ingest_pdf "path/ke/file.pdf" [--reset]')
    pdf = Path(args[0])
    if not pdf.exists():
        raise SystemExit(f"File tidak ada: {pdf}")
    ingest(pdf, reset="--reset" in sys.argv[1:])
