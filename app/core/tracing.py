import time
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache, wraps
from typing import Any, TypeVar, cast

from app.core.config import LANGFUSE_HOST, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY

LANGFUSE_PUBLIC = LANGFUSE_PUBLIC_KEY
LANGFUSE_SECRET = LANGFUSE_SECRET_KEY

F = TypeVar("F", bound=Callable[..., Any])

TIPE_NODE = {
    "rewrite_query": "span",
    "route_intent": "chain",
    "retrieve": "retriever",
    "rerank": "tool",
    "generate": "chain",
    "verify": "evaluator",
    "mutate_strategy": "span",
}


_token: ContextVar[list[dict[str, int]] | None] = ContextVar("_token", default=None)

HARGA_INPUT_PER_JUTA = 0.25
HARGA_OUTPUT_PER_JUTA = 1.50


def catat_token(pemakaian: dict[str, int]) -> None:
    daftar = _token.get()
    if daftar is not None and pemakaian:
        daftar.append(pemakaian)


def ringkas_token() -> dict[str, float]:
    daftar = _token.get() or []
    masuk = sum(t.get("input", 0) for t in daftar)
    keluar = sum(t.get("output", 0) for t in daftar)
    biaya = masuk / 1e6 * HARGA_INPUT_PER_JUTA + keluar / 1e6 * HARGA_OUTPUT_PER_JUTA
    return {
        "panggilan_llm": len(daftar),
        "token_input": masuk,
        "token_output": keluar,
        "token_total": masuk + keluar,
        "biaya_usd": round(biaya, 6),
    }


def aktif() -> bool:
    return bool(LANGFUSE_PUBLIC and LANGFUSE_SECRET)


@lru_cache(maxsize=1)
def _klien() -> Any:
    from langfuse import Langfuse

    return Langfuse(public_key=LANGFUSE_PUBLIC, secret_key=LANGFUSE_SECRET, host=LANGFUSE_HOST)


class _Diam:
    def update(self, **kw: Any) -> None:
        catat_token(kw.get("usage_details") or {})
        return None

    def set_trace_io(self, **_: Any) -> None:
        return None


@contextmanager
def _observasi(nama: str, tipe: str, **kw: Any) -> Iterator[Any]:
    if not aktif():
        yield _Diam()
        return
    try:
        cm = _klien().start_as_current_observation(name=nama, as_type=tipe, **kw)
    except Exception as e:  # noqa: BLE001
        print(f"  [trace] {nama} gagal dicatat: {type(e).__name__}: {str(e)[:120]}")
        yield _Diam()
        return

    # Hanya pembuatan observasi yang dijaga try/except di atas; kalau blok ini ikut
    # dibungkus, exception dari node tertelan dan Python melempar
    # "generator didn't stop after throw()" yang menutupi error aslinya.
    with cm as s:
        yield s


def usage(resp: Any) -> dict[str, int]:
    u = getattr(resp, "usage_metadata", None)
    if not u:
        return {}
    return {
        "input": getattr(u, "prompt_token_count", 0) or 0,
        "output": getattr(u, "candidates_token_count", 0) or 0,
        "total": getattr(u, "total_token_count", 0) or 0,
    }


class _Rekam:
    def __init__(self, span: Any) -> None:
        self._span = span

    def update(self, **kw: Any) -> None:
        catat_token(kw.get("usage_details") or {})
        self._span.update(**kw)


@contextmanager
def generation(nama: str, model: str, masukan: Any) -> Iterator[Any]:
    with _observasi(nama, "generation", model=model, input=masukan) as g:
        yield g if isinstance(g, _Diam) else _Rekam(g)


def _potong(hits: Any, n: int = 8) -> list[str]:
    keluar = []
    for h in (hits or [])[:n]:
        muatan = getattr(h, "payload", None) or {}
        keluar.append(str(muatan.get("chunk_id", "?")))
    return keluar


def _io(nama: str, state: Any, hasil: Any) -> tuple[Any, Any]:
    g, h = (state or {}), (hasil or {})
    if nama == "rewrite_query":
        return {"query": g.get("original_query")}, {
            "rewritten": h.get("rewritten_query"),
            "alias": h.get("alias_terpakai"),
        }
    if nama == "route_intent":
        return {"query": g.get("original_query")}, {
            "intent": h.get("intent"),
            "source_type": h.get("source_type"),
            "top_k": h.get("top_k"),
        }
    if nama == "retrieve":
        return {
            "query": g.get("query_dipakai") or g.get("rewritten_query"),
            "source_type": g.get("source_type"),
        }, {
            "jumlah": len(h.get("retrieved_chunks") or []),
            "chunk_ids": _potong(h.get("retrieved_chunks")),
        }
    if nama == "rerank":
        return {"kandidat": len(g.get("retrieved_chunks") or [])}, {
            "chunk_ids": _potong(h.get("reranked_chunks"))
        }
    if nama == "generate":
        return {"chunk_ids": _potong(g.get("reranked_chunks"))}, {
            "answer": str(h.get("answer", ""))[:1500],
            "degraded_mode": h.get("degraded_mode", False),
        }
    if nama == "verify":
        return {"answer": str(g.get("answer", ""))[:1000]}, {
            "verdict": h.get("verdict"),
            "unsupported_claims": h.get("unsupported_claims"),
            "supporting_chunk_ids": h.get("supporting_chunk_ids"),
            "reasoning": h.get("reasoning"),
        }
    if nama == "mutate_strategy":
        riwayat = h.get("strategy_history") or [{}]
        return {"percobaan_ke": h.get("retry_count")}, riwayat[-1]
    return None, None


# Span dibuka SEBELUM node jalan, bukan disusun ulang di akhir: kalau disusun
# belakangan, Langfuse mencatat durasi nol untuk semua span.
def ukur(nama: str) -> Callable[[F], F]:
    def bungkus(fn: F) -> F:
        @wraps(fn)
        def jalan(state: Any) -> Any:
            mulai = time.perf_counter()
            with _observasi(nama, TIPE_NODE.get(nama, "span")) as s:
                try:
                    hasil = fn(state)
                except Exception as e:
                    lama = (time.perf_counter() - mulai) * 1000
                    s.update(level="ERROR", status_message=f"{type(e).__name__}: {str(e)[:200]}")
                    print(f"  [trace] {nama} gagal setelah {lama:.0f} ms")
                    raise
                lama = (time.perf_counter() - mulai) * 1000
                masuk, keluar = _io(nama, state, hasil)
                s.update(input=masuk, output=keluar, metadata={"ms": round(lama, 1)})
            return {**hasil, "trace": [{"node": nama, "ms": round(lama, 1)}]}

        return cast(F, jalan)

    return bungkus


@contextmanager
def permintaan(pertanyaan: str) -> Iterator[Any]:
    _token.set([])
    with _observasi("tanya-regdocs", "agent", input={"question": pertanyaan}) as s:
        yield s


def tutup(span: Any, pertanyaan: str, state: Mapping[str, Any]) -> None:
    if not aktif():
        return
    try:
        total = sum(t["ms"] for t in state.get("trace", []))
        span.update(
            output={"answer": str(state.get("answer", ""))[:2000]},
            metadata={
                "intent": state.get("intent"),
                "degraded_mode": state.get("degraded_mode", False),
                "verdict": state.get("verdict"),
                "retry_count": state.get("retry_count", 0),
                "total_ms": round(total, 1),
                "jumlah_sitasi": len(state.get("citations", [])),
                "alias_terpakai": state.get("alias_terpakai", []),
            },
        )
        span.set_trace_io(
            input={"question": pertanyaan},
            output={"answer": str(state.get("answer", ""))[:2000]},
        )
    except Exception as e:  # noqa: BLE001
        print(f"  [trace] gagal menutup trace: {type(e).__name__}: {str(e)[:120]}")


# WAJIB dipanggil SETELAH span akar ditutup; kalau dipanggil di dalam blok span akar,
# span itu belum berakhir saat pengiriman jalan dan trace terkirim tanpa nama.
def flush() -> None:
    if not aktif():
        return
    try:
        _klien().flush()
    except Exception as e:  # noqa: BLE001
        print(f"  [trace] gagal flush: {type(e).__name__}: {str(e)[:120]}")
