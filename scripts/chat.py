"""Chat loop CLI. Ambil 3 chunk, suruh Gemini menjawab hanya dari situ.

Dijalankan sebagai modul (`-m`), bukan sebagai file, supaya `app/` ikut
terbaca dari root proyek:

    uv run python -m scripts.chat
    uv run python -m scripts.chat "apa itu perizinan berusaha berbasis risiko"
    uv run python -m scripts.chat --faq "kenapa ID izin PB-UMKU hilang"
    uv run python -m scripts.chat --regulasi "kewajiban pelaku usaha risiko tinggi"

Sejak Tahap 2 jawaban selalu datang bersama sitasi yang bisa kamu buka
sendiri: nomor halaman untuk regulasi, kategori dan tanggal untuk FAQ.
Itu satu-satunya cara membuktikan sistem ini tidak mengarang.
"""

import sys

from app.core.citation import citation
from app.core.generate import jawab
from app.retrieval.search import search


def answer(question: str, source_type: str | None = None) -> str:
    hits = search(question, source_type=source_type)
    if not hits:
        return "Tidak ada dokumen yang cocok. Sudah jalankan `make ingest`?"

    baris = []
    for i, h in enumerate(hits, 1):
        if not h.payload:
            continue
        baris.append(f"  [{i}] {citation(h.payload)}  (skor {h.score:.3f})")
        # pertanyaan asli FAQ ditampilkan di CLI supaya sitasinya bisa dinilai
        # sekilas; di API dia jadi field tersendiri, bukan bagian teks sitasi
        if h.payload.get("question"):
            baris.append(f"      {h.payload['question']}")
    sumber = "\n".join(baris)
    return f"{jawab(question, hits)}\n\nSumber:\n{sumber}"


def main(argv: list[str]) -> None:
    source_type = None
    if "--faq" in argv:
        source_type = "faq"
    elif "--regulasi" in argv:
        source_type = "regulasi"
    sisa = [a for a in argv if not a.startswith("--")]

    if sisa:
        print(answer(" ".join(sisa), source_type))
        return

    print("Ketik pertanyaan. Enter kosong atau Ctrl+C untuk keluar.\n")
    while True:
        try:
            question = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not question:
            return
        print(f"\n{answer(question, source_type)}\n")


if __name__ == "__main__":
    main(sys.argv[1:])
