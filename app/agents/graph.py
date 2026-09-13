"""Perakitan graph. Alurnya lurus di Tahap 9; percabangan baru di Tahap 10.

Kenapa dipindah ke graph padahal alurnya masih lurus: Tahap 10 menambahkan
node verifikasi yang bisa memutuskan untuk mencoba ulang dengan strategi
berbeda. Loop seperti itu tidak bisa ditulis sebagai rangkaian pemanggilan
fungsi biasa tanpa berubah jadi kekusutan if-else. Struktur graph dibangun
sekarang, saat isinya masih bisa dibaca sekali lihat.

Dua panggilan LLM terjadi sebelum pencarian: satu untuk routing, satu lagi
untuk perluasan istilah kalau `ekspansi_llm` dinyalakan.
"""

from functools import lru_cache
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents.nodes import generate, rerank_node, retrieve, rewrite_query, route_intent
from app.agents.state import GraphState


@lru_cache(maxsize=1)
def bangun() -> Any:
    g = StateGraph(GraphState)
    g.add_node("rewrite_query", rewrite_query)
    g.add_node("route_intent", route_intent)
    g.add_node("retrieve", retrieve)
    g.add_node("rerank", rerank_node)
    g.add_node("generate", generate)

    g.add_edge(START, "rewrite_query")
    g.add_edge("rewrite_query", "route_intent")
    g.add_edge("route_intent", "retrieve")
    g.add_edge("retrieve", "rerank")
    g.add_edge("rerank", "generate")
    g.add_edge("generate", END)
    return g.compile()


def tanya(
    question: str,
    rerank: bool = True,
    ekspansi_llm: bool = False,
    top_k: int | None = None,
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
    }
    hasil: GraphState = bangun().invoke(awal)
    if top_k is not None:
        # permintaan eksplisit dari pemanggil menimpa pilihan routing
        hasil["reranked_chunks"] = hasil["reranked_chunks"][:top_k]
        hasil["citations"] = hasil["citations"][:top_k]
    return hasil
