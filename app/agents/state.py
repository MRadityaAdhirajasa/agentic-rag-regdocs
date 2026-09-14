"""Bentuk state yang mengalir lewat graph.

Ini perbedaan inti LangGraph dibanding rantai biasa: bukan output satu
langkah diteruskan ke langkah berikutnya, melainkan **satu objek yang sama
mengalir dan diperbarui tiap node**. Node mana pun boleh membaca apa yang
sudah diisi node sebelumnya.

Itu yang memungkinkan Tahap 10: node verifikasi perlu melihat pertanyaan
asli, hasil pencarian, dan jawaban sekaligus — mustahil kalau tiap langkah
hanya menerima keluaran langkah tepat sebelumnya. Dan saat percobaan diulang,
`strategy_history` menumpuk di state yang sama, sehingga jejak keputusan ikut
terbawa sampai ke respons.
"""

import operator
from typing import Annotated, Any, TypedDict

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

    # verify (Tahap 10, opt-in)
    verify_aktif: bool
    verdict: str
    unsupported_claims: list[str]
    supporting_chunk_ids: list[str]
    reasoning: str

    # mutate_strategy
    retry_count: int
    strategy_history: list[dict[str, Any]]
    query_dipakai: str

    # degraded mode (Tahap 11)
    degraded_mode: bool
    degraded_reason: list[str]

    # pemantauan (Tahap 12). `operator.add` membuat tiap node MENAMBAH
    # catatannya sendiri, bukan menimpa catatan node sebelumnya — dan saat
    # graph berputar, percobaan kedua ikut tercatat, tidak menghapus yang pertama.
    trace: Annotated[list[dict[str, Any]], operator.add]
    token: dict[str, float]
