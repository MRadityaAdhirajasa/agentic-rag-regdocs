"""Node-node graph. Tiap fungsi menerima state dan mengembalikan bagian yang diubah.

Tidak ada kemampuan baru di Tahap 9 — yang sudah jalan dipindah ke bentuk
graph. Yang benar-benar baru cuma `route_intent`, dan itu pun memakai
retrieval yang sama, hanya dengan parameter berbeda.
"""

import logging

from google import genai

from app.agents.state import GraphState
from app.core.citation import citation
from app.core.config import GEMINI_MODEL, GOOGLE_API_KEY, require
from app.core.entities import normalisasi
from app.core.generate import jawab
from app.retrieval.rerank import rerank
from app.retrieval.search import KANDIDAT_RERANK, search

logging.getLogger("google_genai.models").setLevel(logging.ERROR)

INTENT_VALID = ("lookup", "comparison", "summary", "troubleshooting")

# Tiap intent memakai retrieval yang sama, cuma parameternya berbeda.
# `troubleshooting` disaring ke FAQ: "kenapa ikon pensil tidak muncul" tidak
# akan pernah terjawab oleh pasal, dan membiarkan pasal ikut bersaing cuma
# mengisi slot teratas dengan hasil yang tidak relevan.
PARAMETER: dict[str, tuple[str | None, int]] = {
    "lookup": (None, 3),
    "comparison": (None, 6),
    "summary": (None, 6),
    "troubleshooting": ("faq", 3),
}

PROMPT_ROUTE = """Klasifikasikan pertanyaan pengguna ke SATU kategori.

lookup          : menanyakan isi aturan, definisi, syarat, atau kewenangan.
comparison      : membandingkan dua hal atau menanyakan perbedaan.
summary         : minta ringkasan atau gambaran umum suatu bab/topik.
troubleshooting : keluhan pemakaian aplikasi OSS — error, notifikasi, data
                  tidak muncul, tombol tidak ada, cara melakukan langkah di
                  sistem. Jawabannya ada di FAQ, bukan di pasal.

Jawab HANYA dengan satu kata dari empat di atas.

Pertanyaan: {question}
Kategori:"""

PROMPT_EKSPANSI = """Tulis ulang pertanyaan ini agar lebih mudah dicari di
dokumen peraturan Indonesia. Tambahkan istilah hukum yang relevan.
Pertahankan semua singkatan yang sudah ada. Maksimal dua kalimat.
Jawab hanya dengan pertanyaan hasil tulis ulang, tanpa penjelasan.

Pertanyaan: {question}
Tulis ulang:"""


def _llm(prompt: str) -> str:
    client = genai.Client(api_key=require("GOOGLE_API_KEY", GOOGLE_API_KEY))
    resp = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        # suhu nol: hasil yang sama untuk pertanyaan yang sama, supaya cache
        # embedding tetap kena dan routing bisa diukur ulang dengan hasil sama
        config={"temperature": 0.0},
    )
    return str(resp.text).strip()


def rewrite_query(state: GraphState) -> GraphState:
    """Normalkan alias (deterministik), lalu opsional perluas dengan LLM."""
    teks, kena = normalisasi(state["original_query"])
    if state.get("ekspansi_llm"):
        teks = _llm(PROMPT_EKSPANSI.format(question=teks))
    return {"rewritten_query": teks, "alias_terpakai": kena}


def route_intent(state: GraphState) -> GraphState:
    """Tentukan maksud pertanyaan, lalu pilih parameter retrieval-nya.

    Pertanyaan asli yang dipakai, bukan hasil tulis ulang: perluasan istilah
    hukum justru membuat keluhan aplikasi terdengar seperti pertanyaan pasal.
    """
    try:
        jawaban = _llm(PROMPT_ROUTE.format(question=state["original_query"])).lower()
    except Exception as e:  # noqa: BLE001
        # Kuota LLM habis atau layanan mati. Routing yang gagal tidak boleh
        # mematikan permintaan — mundur ke lookup tanpa filter, yang paling
        # tidak merugikan. Degraded mode yang sebenarnya dibangun di Tahap 11.
        print(f"  route_intent mundur ke lookup: {type(e).__name__}")
        jawaban = "lookup"
    intent = next((i for i in INTENT_VALID if i in jawaban), "lookup")
    source_type, top_k = PARAMETER[intent]
    return {"intent": intent, "source_type": source_type, "top_k": top_k}


def retrieve(state: GraphState) -> GraphState:
    """Ambil kandidat. Saat reranking aktif, ambil lebih banyak dulu."""
    jumlah = KANDIDAT_RERANK if state.get("rerank_aktif", True) else state["top_k"]
    hits = search(
        state["rewritten_query"],
        limit=jumlah,
        source_type=state["source_type"],
        rerank=False,
    )
    return {"retrieved_chunks": hits}


def rerank_node(state: GraphState) -> GraphState:
    if not state.get("rerank_aktif", True):
        return {"reranked_chunks": state["retrieved_chunks"][: state["top_k"]]}
    hasil = rerank(state["rewritten_query"], state["retrieved_chunks"], state["top_k"])
    return {"reranked_chunks": hasil}


def generate(state: GraphState) -> GraphState:
    hits = state["reranked_chunks"]
    return {
        "answer": jawab(state["original_query"], hits),
        "citations": [
            {**h.payload, "citation": citation(h.payload), "score": h.score}
            for h in hits
            if h.payload
        ],
    }


def klasifikasi_intent(question: str) -> str:
    """Dipakai `scripts/eval_routing.py` tanpa menjalankan seluruh graph."""
    return route_intent({"original_query": question})["intent"]


__all__ = [
    "INTENT_VALID",
    "PARAMETER",
    "generate",
    "klasifikasi_intent",
    "rerank_node",
    "retrieve",
    "rewrite_query",
    "route_intent",
]
