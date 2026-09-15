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
    g.add_edge("mutate_strategy", "retrieve")
    return g.compile()


def tanya(
    question: str,
    rerank: bool = True,
    ekspansi_llm: bool = False,
    top_k: int | None = None,
    verify: bool = False,
) -> GraphState:
    awal: GraphState = {
        "original_query": question,
        "rerank_aktif": rerank,
        "ekspansi_llm": ekspansi_llm,
        "verify_aktif": verify,
        "retry_count": 0,
        "strategy_history": [],
        "trace": [],
    }
    with tracing.permintaan(question) as akar:
        hasil: GraphState = bangun().invoke(awal)
        tracing.tutup(akar, question, dict(hasil))
        hasil["token"] = tracing.ringkas_token()
    tracing.flush()
    if top_k is not None:
        hasil["reranked_chunks"] = hasil["reranked_chunks"][:top_k]
        hasil["citations"] = hasil["citations"][:top_k]
    return hasil
