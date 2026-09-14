"""Perakitan graph.

Sejak Tahap 10 alurnya tidak lurus lagi. Setelah `generate`, node `verify`
menilai jawaban, dan sebuah **conditional edge** memutuskan: selesai, atau
kembali ke `retrieve` lewat `mutate_strategy` dengan parameter yang sudah
diubah. Inilah alasan sebenarnya struktur graph dipakai — percabangan yang
kembali ke node sebelumnya tidak bisa ditulis sebagai rangkaian pemanggilan
fungsi tanpa berubah jadi kekusutan if-else.

    rewrite -> route -> retrieve -> rerank -> generate -> verify --+
                          ^                                        |
                          |                                        |
                          +---- mutate_strategy <--- "ulangi" -----+
                                                     "selesai" --> END

Ongkos per pertanyaan: 1 panggilan LLM untuk routing, 1 untuk menyusun
jawaban. Kalau `verify` dinyalakan, tambah 1 lagi; dan tiap percobaan ulang
menambah 2 (susun ulang, lalu nilai lagi). Dengan `max_retries = 2`, batas
atasnya 7 panggilan untuk satu pertanyaan. Karena itu verifikasi opt-in.
"""

from functools import lru_cache
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents.nodes import generate, rerank_node, retrieve, rewrite_query, route_intent
from app.agents.state import GraphState
from app.agents.verify import cukup_atau_ulangi, mutate_strategy, verify
from app.core import tracing


@lru_cache(maxsize=1)
def bangun() -> Any:
    g = StateGraph(GraphState)
    # tiap node dibungkus pengukur waktu; angkanya menumpuk di state["trace"]
    g.add_node("rewrite_query", tracing.ukur("rewrite_query")(rewrite_query))
    g.add_node("route_intent", tracing.ukur("route_intent")(route_intent))
    g.add_node("retrieve", tracing.ukur("retrieve")(retrieve))
    g.add_node("rerank", tracing.ukur("rerank")(rerank_node))
    g.add_node("generate", tracing.ukur("generate")(generate))
    g.add_node("verify", tracing.ukur("verify")(verify))
    g.add_node("mutate_strategy", tracing.ukur("mutate_strategy")(mutate_strategy))

    g.add_edge(START, "rewrite_query")
    g.add_edge("rewrite_query", "route_intent")
    g.add_edge("route_intent", "retrieve")
    g.add_edge("retrieve", "rerank")
    g.add_edge("rerank", "generate")
    g.add_edge("generate", "verify")
    g.add_conditional_edges(
        "verify",
        cukup_atau_ulangi,
        {"selesai": END, "ulangi": "mutate_strategy"},
    )
    # kembali ke retrieve, bukan ke rewrite: yang diubah parameter pencarian,
    # bukan pertanyaannya dari awal
    g.add_edge("mutate_strategy", "retrieve")
    return g.compile()


def tanya(
    question: str,
    rerank: bool = True,
    ekspansi_llm: bool = False,
    top_k: int | None = None,
    verify: bool = False,
) -> GraphState:
    """Jalankan graph untuk satu pertanyaan, kembalikan state akhirnya.

    Yang dikembalikan state penuh, bukan cuma jawabannya — `intent`,
    `rewritten_query`, dan `alias_terpakai` ikut terbawa supaya keputusan
    sistem bisa diperiksa, bukan cuma hasil akhirnya.
    """
    awal: GraphState = {
        "original_query": question,
        "rerank_aktif": rerank,
        "ekspansi_llm": ekspansi_llm,
        "verify_aktif": verify,
        "retry_count": 0,
        "strategy_history": [],
        "trace": [],
    }
    # span akar dibuka SEBELUM invoke: span tiap node bersarang di bawahnya
    # lewat context OpenTelemetry, bukan disusun ulang setelah selesai
    with tracing.permintaan(question) as akar:
        hasil: GraphState = bangun().invoke(awal)
        tracing.tutup(akar, question, dict(hasil))
        hasil["token"] = tracing.ringkas_token()
    # flush di LUAR blok: span akar baru berakhir saat blok ditutup
    tracing.flush()
    if top_k is not None:
        # permintaan eksplisit dari pemanggil menimpa pilihan routing
        hasil["reranked_chunks"] = hasil["reranked_chunks"][:top_k]
        hasil["citations"] = hasil["citations"][:top_k]
    return hasil
