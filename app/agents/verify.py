"""Node verifikasi dan mutasi strategi.

Verifikasi memakai LLM untuk menilai jawaban terhadap potongan yang dipakai
menyusunnya — LLM-as-a-judge. Sengaja opt-in (`verify=false` secara bawaan):
dia menambah satu panggilan LLM per percobaan, dan tiap percobaan ulang
menambah dua lagi (susun jawaban, lalu nilai lagi).

Aturan keras dari roadmap: **tiap percobaan ulang wajib mengubah minimal satu
parameter.** Kalau tidak, mengulang cuma membuang kuota untuk mendapatkan
hasil yang sama persis. Aturan itu ditegakkan lewat pemeriksaan di
`mutate_strategy`, bukan lewat komentar yang bisa dilupakan.
"""

import logging
from typing import Literal

from google import genai
from pydantic import BaseModel

from app.agents.state import GraphState
from app.core import budget
from app.core.config import GEMINI_MODEL, GOOGLE_API_KEY, require
from app.core.errors import LayananTidakTersedia

logging.getLogger("google_genai.models").setLevel(logging.ERROR)

MAX_RETRIES = 2

VERDICT_CUKUP = ("supported", "partial")

# Prompt penyusun jawaban memerintahkan "bilang tidak tahu" kalau konteksnya
# tidak memuat jawaban, jadi frasa ini kita yang kendalikan — bukan tebakan
# atas bahasa bebas model.
PENOLAKAN = ("tidak tahu", "tidak diketahui", "tidak ditemukan dalam konteks")


class Penilaian(BaseModel):
    """Bentuk keluaran verifikasi. Dipaksakan lewat response_schema, bukan diparse manual."""

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
    resp = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=PROMPT_VERIFY.format(context=context, question=question, answer=answer),
        config={
            "response_mime_type": "application/json",
            "response_schema": Penilaian,
            "temperature": 0.0,
        },
    )
    budget.pakai()
    hasil = resp.parsed
    if not isinstance(hasil, Penilaian):
        potongan = (resp.text or "")[:200]
        raise RuntimeError(f"Verifikasi tidak mengembalikan bentuk yang benar: {potongan}")
    return hasil


def verify(state: GraphState) -> GraphState:
    if not state.get("verify_aktif"):
        return {"verdict": "tidak_diverifikasi"}

    # Penolakan dikenali tanpa memanggil LLM: lebih andal, dan menghemat satu
    # panggilan pada jalur yang justru paling sering diulang.
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

    # potongan dinomori supaya penilai cukup menyebut angka; meminta dia
    # menyalin chunk_id panjang mengundang salah ketik yang tidak terdeteksi
    context = "\n\n".join(f"[{i}] {h.payload['text']}" for i, h in enumerate(hits, 1) if h.payload)
    try:
        hasil = _nilai(state["original_query"], state["answer"], context)
    except Exception as e:  # noqa: BLE001
        # Penilai yang mati tidak boleh menjatuhkan permintaan. Yang jujur
        # adalah mengaku belum dinilai, bukan mengaku sudah lolos.
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
    """Ubah parameter pencarian sebelum mencoba lagi. Wajib berubah.

    Percobaan 1 melebarkan jangkauan: filter sumber dibuang dan lebih banyak
    potongan diambil. Percobaan 2 kembali ke pertanyaan asli — perluasan alias
    kadang justru menggeser makna pertanyaan pendek.
    """
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

    if (top_k_baru, sumber_baru, query_baru) == (top_k_lama, sumber_lama, query_lama):
        # Aturan roadmap ditegakkan di sini: mengulang tanpa mengubah apa pun
        # hanya membuang kuota untuk hasil yang sama persis.
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
    """Conditional edge: ini yang membuat graph bisa berputar, bukan cuma lurus."""
    if state.get("verdict") in VERDICT_CUKUP or not state.get("verify_aktif"):
        return "selesai"
    if state.get("verdict") in ("gagal_diverifikasi", "tidak_diverifikasi"):
        return "selesai"
    if state.get("retry_count", 0) >= MAX_RETRIES:
        return "selesai"
    return "ulangi"


__all__: list[str] = ["MAX_RETRIES", "Penilaian", "cukup_atau_ulangi", "mutate_strategy", "verify"]
