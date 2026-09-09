"""Chat loop CLI. Ambil 3 chunk, suruh Gemini menjawab hanya dari situ.

Dijalankan sebagai modul (`-m`), bukan sebagai file, supaya `app/` ikut
terbaca dari root proyek:

    uv run python -m scripts.chat
    uv run python -m scripts.chat "apa itu perizinan berusaha berbasis risiko"
"""

import logging
import sys

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


def answer(question: str) -> str:
    hits = search(question)
    if not hits:
        return "Tidak ada dokumen di collection. Jalankan ingestion dulu."

    context = "\n\n---\n\n".join(str(h.payload["text"]) for h in hits if h.payload)
    client = genai.Client(api_key=require("GOOGLE_API_KEY", GOOGLE_API_KEY))
    resp = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=PROMPT.format(context=context, question=question),
    )
    sumber = "\n".join(
        f"  [{i + 1}] {h.payload['chunk_id']} (skor {h.score:.3f})"
        for i, h in enumerate(hits)
        if h.payload
    )
    return f"{resp.text}\n\nSumber:\n{sumber}"


def main() -> None:
    if len(sys.argv) > 1:
        print(answer(" ".join(sys.argv[1:])))
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
        print(f"\n{answer(question)}\n")


if __name__ == "__main__":
    main()
