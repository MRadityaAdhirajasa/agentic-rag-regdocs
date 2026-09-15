import logging
from typing import Literal

from google import genai
from pydantic import BaseModel

from app.agents.state import GraphState
from app.core import budget, tracing
from app.core.config import GEMINI_MODEL, GOOGLE_API_KEY, require
from app.core.errors import LayananTidakTersedia

logging.getLogger("google_genai.models").setLevel(logging.ERROR)

MAX_RETRIES = 2

VERDICT_CUKUP = ("supported", "partial")

PENOLAKAN = ("tidak tahu", "tidak diketahui", "tidak ditemukan dalam konteks")


class Penilaian(BaseModel):
    verdict: Literal["supported", "partial", "unsupported"]
    unsupported_claims: list[str]
    supporting_chunk_numbers: list[int]
    reasoning: str


PROMPT_VERIFY = """Kamu penilai. Periksa apakah JAWABAN benar-benar didukung KONTEKS.

Jawaban yang menyatakan tidak tahu sudah disaring sebelum sampai ke kamu,
jadi anggap jawaban di bawah selalu berisi klaim.

verdict:
  supported   : seluruh klaim dalam jawaban ada dasarnya di konteks.
  partial     : sebagian klaim didukung, sebagian tidak.
  unsupported : klaim utamanya tidak punya dasar di konteks.

unsupported_claims       : kalimat jawaban yang tidak ada dasarnya. Kosongkan kalau tidak ada.
supporting_chunk_numbers : nomor potongan yang benar-benar mendukung jawaban.
reasoning                : satu kalimat alasan.

KONTEKS:
{context}

PERTANYAAN: {question}

JAWABAN: {answer}"""


def _nilai(question: str, answer: str, context: str) -> Penilaian:
    if budget.habis():
        raise LayananTidakTersedia("Gemini", "budget LLM harian aplikasi habis")
    client = genai.Client(api_key=require("GOOGLE_API_KEY", GOOGLE_API_KEY))
    with tracing.generation(
        "nilai-jawaban", GEMINI_MODEL, {"question": question, "answer": answer}
    ) as g:
        resp = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=PROMPT_VERIFY.format(context=context, question=question, answer=answer),
            config={
                "response_mime_type": "application/json",
                "response_schema": Penilaian,
                "temperature": 0.0,
            },
        )
        g.update(output=str(resp.text), usage_details=tracing.usage(resp))
    budget.pakai()
    hasil = resp.parsed
    if not isinstance(hasil, Penilaian):
        potongan = (resp.text or "")[:200]
        raise RuntimeError(f"Verifikasi tidak mengembalikan bentuk yang benar: {potongan}")
    return hasil


def verify(state: GraphState) -> GraphState:
    if not state.get("verify_aktif"):
        return {"verdict": "tidak_diverifikasi"}

    jawaban = state.get("answer", "").strip().lower()
    if any(jawaban.startswith(p) or jawaban == p + "." for p in PENOLAKAN):
        return {
            "verdict": "unsupported",
            "unsupported_claims": [],
            "supporting_chunk_ids": [],
            "reasoning": "Jawaban menyatakan tidak tahu; korpus tidak memuat jawabannya.",
        }

    hits = state["reranked_chunks"]
    if not hits:
        return {
            "verdict": "unsupported",
            "unsupported_claims": [],
            "supporting_chunk_ids": [],
            "reasoning": "Tidak ada potongan yang terambil.",
        }

    context = "\n\n".join(f"[{i}] {h.payload['text']}" for i, h in enumerate(hits, 1) if h.payload)
    try:
        hasil = _nilai(state["original_query"], state["answer"], context)
    except Exception as e:  # noqa: BLE001
        print(f"  verify gagal, dilewati: {type(e).__name__}")
        return {"verdict": "gagal_diverifikasi", "reasoning": str(e)[:200]}

    ids = []
    for n in hasil.supporting_chunk_numbers:
        if 1 <= n <= len(hits):
            muatan = hits[n - 1].payload
            if muatan:
                ids.append(str(muatan["chunk_id"]))
    return {
        "verdict": hasil.verdict,
        "unsupported_claims": hasil.unsupported_claims,
        "supporting_chunk_ids": ids,
        "reasoning": hasil.reasoning,
    }


def mutate_strategy(state: GraphState) -> GraphState:
    percobaan = state.get("retry_count", 0) + 1
    top_k_lama = state["top_k"]
    sumber_lama = state["source_type"]
    query_lama = state.get("query_dipakai", state["rewritten_query"])

    if percobaan == 1:
        top_k_baru = max(top_k_lama * 2, 6)
        sumber_baru: str | None = None
        query_baru = query_lama
        perubahan = "lebarkan: buang filter sumber, gandakan top_k"
    else:
        top_k_baru = max(top_k_lama, 8)
        sumber_baru = None
        query_baru = state["original_query"]
        perubahan = "kembali ke pertanyaan asli tanpa perluasan alias"

    # Mengulang tanpa mengubah apa pun cuma membuang kuota untuk hasil yang sama persis.
    if (top_k_baru, sumber_baru, query_baru) == (top_k_lama, sumber_lama, query_lama):
        raise RuntimeError(f"Percobaan {percobaan} tidak mengubah satu pun parameter.")

    riwayat = list(state.get("strategy_history", []))
    riwayat.append(
        {
            "percobaan": percobaan,
            "perubahan": perubahan,
            "top_k": top_k_baru,
            "source_type": sumber_baru,
            "query": query_baru,
        }
    )
    print(f"  retry {percobaan}: {perubahan}")

    return {
        "retry_count": percobaan,
        "top_k": top_k_baru,
        "source_type": sumber_baru,
        "query_dipakai": query_baru,
        "strategy_history": riwayat,
    }


def cukup_atau_ulangi(state: GraphState) -> str:
    if state.get("verdict") in VERDICT_CUKUP or not state.get("verify_aktif"):
        return "selesai"
    if state.get("verdict") in ("gagal_diverifikasi", "tidak_diverifikasi"):
        return "selesai"
    if state.get("retry_count", 0) >= MAX_RETRIES:
        return "selesai"
    return "ulangi"


__all__: list[str] = ["MAX_RETRIES", "Penilaian", "cukup_atau_ulangi", "mutate_strategy", "verify"]
