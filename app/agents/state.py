import operator
from typing import Annotated, Any, TypedDict

from qdrant_client.models import ScoredPoint


class GraphState(TypedDict, total=False):
    original_query: str
    rerank_aktif: bool
    ekspansi_llm: bool

    rewritten_query: str
    alias_terpakai: list[str]

    intent: str
    source_type: str | None
    top_k: int

    retrieved_chunks: list[ScoredPoint]
    reranked_chunks: list[ScoredPoint]

    answer: str
    citations: list[dict[str, Any]]

    verify_aktif: bool
    verdict: str
    unsupported_claims: list[str]
    supporting_chunk_ids: list[str]
    reasoning: str

    retry_count: int
    strategy_history: list[dict[str, Any]]
    query_dipakai: str

    degraded_mode: bool
    degraded_reason: list[str]

    trace: Annotated[list[dict[str, Any]], operator.add]
    token: dict[str, float]
