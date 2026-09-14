"""Menyusun jawaban dari potongan yang sudah ditemukan.

Dipisah dari CLI sejak Tahap 8: CLI dan API harus memakai prompt yang sama
persis, kalau tidak jawaban keduanya bisa berbeda untuk pertanyaan yang sama
dan tidak ada yang tahu mana yang benar.

Retrieval tidak dikerjakan di sini — fungsi ini menerima potongan yang sudah
jadi. Pemisahan itu yang membuat Tahap 9 bisa menukar cara mencari tanpa
menyentuh cara menjawab.
"""

import logging

from google import genai
from qdrant_client.models import ScoredPoint

from app.core import budget, tracing
from app.core.config import GEMINI_MODEL, GOOGLE_API_KEY, require
from app.core.errors import LayananTidakTersedia

# SDK menyarankan Chat.send_message untuk function calling; kita tidak pakai
# function calling sama sekali, jadi peringatannya cuma bising.
logging.getLogger("google_genai.models").setLevel(logging.ERROR)

# Pagar keras: jawaban yang meluber bukan cuma mahal, tapi juga tanda model
# sedang mengarang alih-alih mengutip.
MAX_OUTPUT_TOKENS = 800

PROMPT = """Jawab pertanyaan HANYA berdasarkan konteks di bawah.
Kalau konteksnya tidak memuat jawabannya, bilang tidak tahu. Jangan mengarang.

Konteks:
{context}

Pertanyaan: {question}
Jawaban:"""


def jawab(question: str, hits: list[ScoredPoint]) -> str:
    if not hits:
        return "Tidak ada dokumen yang cocok. Sudah jalankan `make ingest`?"

    if budget.habis():
        raise LayananTidakTersedia("Gemini", "budget LLM harian aplikasi habis")

    context = "\n\n---\n\n".join(str(h.payload["text"]) for h in hits if h.payload)
    client = genai.Client(api_key=require("GOOGLE_API_KEY", GOOGLE_API_KEY))
    with tracing.generation("susun-jawaban", GEMINI_MODEL, {"question": question}) as g:
        resp = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=PROMPT.format(context=context, question=question),
            config={"max_output_tokens": MAX_OUTPUT_TOKENS},
        )
        g.update(output=str(resp.text), usage_details=tracing.usage(resp))
    budget.pakai()
    teks = str(resp.text).strip()
    # prompt diakhiri "Jawaban:" dan model kadang mengulanginya di awal balasan
    return teks.removeprefix("Jawaban:").lstrip()
