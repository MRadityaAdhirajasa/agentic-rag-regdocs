"""Node-node graph. Tiap fungsi menerima state dan mengembalikan bagian yang diubah.

Tidak ada kemampuan baru di Tahap 9 — yang sudah jalan dipindah ke bentuk
graph. Yang benar-benar baru cuma `route_intent`, dan itu pun memakai
retrieval yang sama, hanya dengan parameter berbeda.
"""

import logging

from google import genai
from qdrant_client.models import ScoredPoint

from app.agents.state import GraphState
from app.core import budget, tracing
from app.core.citation import citation
from app.core.config import GEMINI_MODEL, GOOGLE_API_KEY, require
from app.core.entities import normalisasi
from app.core.errors import LayananTidakTersedia
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


def _llm(prompt: str, nama: str = "llm") -> str:
    if budget.habis():
        raise LayananTidakTersedia("Gemini", "budget LLM harian aplikasi habis")
    client = genai.Client(api_key=require("GOOGLE_API_KEY", GOOGLE_API_KEY))
    with tracing.generation(nama, GEMINI_MODEL, {"prompt": prompt[-600:]}) as g:
        resp = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            # suhu nol: hasil yang sama untuk pertanyaan yang sama, supaya cache
            # embedding tetap kena dan routing bisa diukur ulang dengan hasil sama
            config={"temperature": 0.0},
        )
        g.update(output=str(resp.text), usage_details=tracing.usage(resp))
    budget.pakai()
    return str(resp.text).strip()


def rewrite_query(state: GraphState) -> GraphState:
    """Normalkan alias (deterministik), lalu opsional perluas dengan LLM."""
    teks, kena = normalisasi(state["original_query"])
    if state.get("ekspansi_llm"):
        teks = _llm(PROMPT_EKSPANSI.format(question=teks), "perluas-istilah")
    return {"rewritten_query": teks, "alias_terpakai": kena}


def route_intent(state: GraphState) -> GraphState:
    """Tentukan maksud pertanyaan, lalu pilih parameter retrieval-nya.

    Pertanyaan asli yang dipakai, bukan hasil tulis ulang: perluasan istilah
    hukum justru membuat keluhan aplikasi terdengar seperti pertanyaan pasal.
    """
    try:
        jawaban = _llm(
            PROMPT_ROUTE.format(question=state["original_query"]), "klasifikasi-intent"
        ).lower()
    except Exception as e:  # noqa: BLE001
        # Routing yang gagal tidak boleh mematikan permintaan. Mundur ke
        # lookup tanpa filter — pilihan yang paling tidak merugikan, karena
        # tidak membuang satu pun sumber dari pencarian.
        print(f"  route_intent mundur ke lookup: {type(e).__name__}")
        source_type, top_k = PARAMETER["lookup"]
        return {
            "intent": "lookup",
            "source_type": source_type,
            "top_k": top_k,
            "degraded_mode": True,
            "degraded_reason": [*state.get("degraded_reason", []), f"routing: {e}"],
        }
    intent = next((i for i in INTENT_VALID if i in jawaban), "lookup")
    source_type, top_k = PARAMETER[intent]
    return {"intent": intent, "source_type": source_type, "top_k": top_k}


def retrieve(state: GraphState) -> GraphState:
    """Ambil kandidat. Saat reranking aktif, ambil lebih banyak dulu."""
    jumlah = KANDIDAT_RERANK if state.get("rerank_aktif", True) else state["top_k"]
    # `query_dipakai` bisa diganti mutate_strategy saat percobaan ulang;
    # pada percobaan pertama isinya sama dengan hasil rewrite
    kalimat = state.get("query_dipakai") or state["rewritten_query"]
    try:
        hits = search(kalimat, limit=jumlah, source_type=state["source_type"], rerank=False)
    except LayananTidakTersedia as e:
        # Tanpa embedding, sisi dense mati total. Yang tersisa BM25 — dan itu
        # jalan sepenuhnya di komputer sendiri, jadi pencarian tetap bisa.
        # Mutunya turun, tapi pasal yang relevan tetap keluar.
        print(f"  retrieve turun ke sparse-only: {e}")
        hits = search(
            kalimat, limit=jumlah, source_type=state["source_type"], rerank=False, mode="sparse"
        )
        return {
            "retrieved_chunks": hits,
            "query_dipakai": kalimat,
            "degraded_mode": True,
            "degraded_reason": [*state.get("degraded_reason", []), f"embedding: {e}"],
        }
    return {"retrieved_chunks": hits, "query_dipakai": kalimat}


def rerank_node(state: GraphState) -> GraphState:
    if not state.get("rerank_aktif", True):
        return {"reranked_chunks": state["retrieved_chunks"][: state["top_k"]]}
    kalimat = state.get("query_dipakai") or state["rewritten_query"]
    hasil = rerank(kalimat, state["retrieved_chunks"], state["top_k"])
    return {"reranked_chunks": hasil}


def _ringkas_tanpa_llm(hits: list[ScoredPoint]) -> str:
    """Jawaban pengganti saat LLM mati: kutipan mentah, tanpa dirangkai.

    Sengaja tidak menyusun kalimat sendiri. Merangkai tanpa model justru
    berisiko menyiratkan kesimpulan yang tidak ada di teksnya.
    """
    if not hits:
        return "Layanan penyusun jawaban sedang tidak tersedia, dan tidak ada potongan yang cocok."
    baris = [
        "Layanan penyusun jawaban sedang tidak tersedia. Berikut potongan aturan "
        "yang paling relevan, silakan baca langsung:",
        "",
    ]
    for i, h in enumerate(hits, 1):
        if h.payload:
            baris.append(f"[{i}] {citation(h.payload)}")
            baris.append(f"    {str(h.payload['text'])[:400]}")
    return "\n".join(baris)


def generate(state: GraphState) -> GraphState:
    hits = state["reranked_chunks"]
    try:
        teks = jawab(state["original_query"], hits)
        turun: GraphState = {}
    except Exception as e:  # noqa: BLE001
        # Inti Tahap 11: tanpa LLM, sistem tetap mengembalikan pasal yang
        # relevan. Yang hilang cuma perangkaian kalimatnya.
        print(f"  generate turun ke kutipan mentah: {type(e).__name__}")
        teks = _ringkas_tanpa_llm(hits)
        turun = {
            "degraded_mode": True,
            "degraded_reason": [*state.get("degraded_reason", []), f"generate: {e}"],
        }
    return {
        **turun,
        "answer": teks,
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
