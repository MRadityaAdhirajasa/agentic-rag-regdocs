"""Bentuk state yang mengalir lewat graph.

Ini perbedaan inti LangGraph dibanding rantai biasa: bukan output satu
langkah diteruskan ke langkah berikutnya, melainkan **satu objek yang sama
mengalir dan diperbarui tiap node**. Node mana pun boleh membaca apa yang
sudah diisi node sebelumnya.

Itu yang memungkinkan Tahap 10: node verifikasi perlu melihat pertanyaan
asli, hasil pencarian, dan jawaban sekaligus — mustahil kalau tiap langkah
hanya menerima keluaran langkah tepat sebelumnya.
"""

from typing import Any, TypedDict

from qdrant_client.models import ScoredPoint


class GraphState(TypedDict, total=False):
    # diisi di awal
    original_query: str
    rerank_aktif: bool
    ekspansi_llm: bool

    # rewrite_query
    rewritten_query: str
    alias_terpakai: list[str]

    # route_intent
    intent: str
    source_type: str | None
    top_k: int

    # retrieve / rerank
    retrieved_chunks: list[ScoredPoint]
    reranked_chunks: list[ScoredPoint]

    # generate
    answer: str
    citations: list[dict[str, Any]]
