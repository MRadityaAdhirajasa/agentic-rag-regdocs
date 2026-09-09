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

import logging
import sys
from typing import Any

from google import genai

from app.core.config import GEMINI_MODEL, GOOGLE_API_KEY, require
from app.retrieval.search import search

# SDK menyarankan Chat.send_message untuk function calling; kita tidak pakai
# function calling sama sekali, jadi peringatannya cuma bising.
logging.getLogger("google_genai.models").setLevel(logging.ERROR)

PROMPT = """Jawab pertanyaan HANYA berdasarkan konteks di bawah.
Kalau konteksnya tidak memuat jawabannya, bilang tidak tahu. Jangan mengarang.

Konteks:
{context}

Pertanyaan: {question}
Jawaban:"""


def citation(payload: dict[str, Any]) -> str:
    """Sitasi dibentuk berbeda per jenis sumber, karena yang bisa diverifikasi berbeda.

    Regulasi bisa dibuka di halaman tertentu. FAQ tidak punya halaman, yang
    relevan justru kategori dan kapan halamannya diakses — isinya bisa berubah.
    """
    if payload.get("source_type") == "faq":
        return (
            f"FAQ OSS — {payload['faq_category']}, diakses {payload['tanggal_akses']}"
            f"\n      {payload['question']}"
        )
    status = payload.get("status", "")
    tanda = "" if status == "berlaku" else f" [status: {status}]"
    return (
        f"{payload['jenis']} {payload['nomor']}/{payload['tahun']}, "
        f"hal. {payload['halaman']}{tanda}"
    )


def answer(question: str, source_type: str | None = None) -> str:
    hits = search(question, source_type=source_type)
    if not hits:
        return "Tidak ada dokumen yang cocok. Sudah jalankan `make ingest`?"

    context = "\n\n---\n\n".join(str(h.payload["text"]) for h in hits if h.payload)
    client = genai.Client(api_key=require("GOOGLE_API_KEY", GOOGLE_API_KEY))
    resp = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=PROMPT.format(context=context, question=question),
    )
    sumber = "\n".join(
        f"  [{i + 1}] {citation(h.payload)}  (skor {h.score:.3f})"
        for i, h in enumerate(hits)
        if h.payload
    )
    return f"{resp.text}\n\nSumber:\n{sumber}"


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
