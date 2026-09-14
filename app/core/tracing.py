"""Pemantauan: lama tiap node, plus trace bersarang ke Langfuse kalau disetel.

Dua sasaran, dan yang pertama lebih penting daripada yang kedua:

1. **Angka latensi per node** ikut terbawa di respons API. Inilah bahan tabel
   benchmark Tahap 13 — p50, p95, dan perbandingan verify on/off. Bahan itu
   tetap ada meski Langfuse tidak pernah dipasang.
2. **Langfuse** sebagai tempat menumpuknya trace dari banyak permintaan.
   Opsional: tanpa `LANGFUSE_PUBLIC_KEY` dan `LANGFUSE_SECRET_KEY`, seluruh
   modul ini diam dan tidak menambah satu milidetik pun.

Span dibuka **sebelum** node jalan dan ditutup sesudahnya, bukan disusun ulang
di akhir. Bedanya menentukan: kalau disusun belakangan, Langfuse mencatat
durasi nol untuk semua span, dan seluruh gunanya — melihat langkah mana yang
lambat — hilang.

Bersarangnya mengandalkan context OpenTelemetry: span node otomatis jadi anak
dari span permintaan, dan generation otomatis jadi anak dari span node,
selama semuanya jalan di thread yang sama.
"""

import time
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache, wraps
from typing import Any, TypeVar, cast

from app.core.config import LANGFUSE_HOST, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY

# Nilainya diambil dari app/core/config.py, bukan dibaca langsung dari env di
# sini. Alasannya nyata, bukan kerapian: modul ini bisa dimuat sebelum
# load_dotenv() jalan, dan key-nya akan terbaca kosong padahal .env sudah benar.
LANGFUSE_PUBLIC = LANGFUSE_PUBLIC_KEY
LANGFUSE_SECRET = LANGFUSE_SECRET_KEY

# TypeVar supaya tipe node tetap utuh setelah dibungkus — LangGraph
# memeriksa tanda tangan node-nya, jadi Callable[[Any], Any] ditolak.
F = TypeVar("F", bound=Callable[..., Any])

# Tipe observasi per node. Langfuse memakainya untuk analitik dan Agent Graph;
# menandai semuanya "span" membuang informasi yang sudah kita punya.
TIPE_NODE = {
    "rewrite_query": "span",
    "route_intent": "chain",
    "retrieve": "retriever",
    "rerank": "tool",
    "generate": "chain",
    "verify": "evaluator",
    "mutate_strategy": "span",
}


# Jumlah token per permintaan, ditampung lokal supaya tetap terukur meski
# Langfuse tidak dipasang. Ini bahan kolom token dan biaya di tabel benchmark.
# ContextVar, bukan variabel modul biasa: dua permintaan yang jalan bersamaan
# tidak boleh saling menambah hitungan.
_token: ContextVar[list[dict[str, int]] | None] = ContextVar("_token", default=None)

# Harga tier berbayar gemini-3.1-flash-lite, USD per 1 juta token.
# Proyek ini jalan di tier gratis; angka ini untuk menjawab "kalau dibayar,
# berapa?" — bukan tagihan sungguhan.
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
    # diimpor di dalam fungsi, bukan di atas berkas: Langfuse membaca env saat
    # dibuat, jadi dia harus lahir setelah load_dotenv() selesai
    from langfuse import Langfuse

    return Langfuse(public_key=LANGFUSE_PUBLIC, secret_key=LANGFUSE_SECRET, host=LANGFUSE_HOST)


class _Diam:
    """Pengganti span saat Langfuse mati. Semua panggilan tidak melakukan apa-apa."""

    def update(self, **kw: Any) -> None:
        # token tetap dicatat meski Langfuse mati — tabel benchmark butuh
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
        # Pemantauan yang menjatuhkan permintaan adalah pemantauan yang salah.
        print(f"  [trace] {nama} gagal dicatat: {type(e).__name__}: {str(e)[:120]}")
        yield _Diam()
        return

    # Hanya PEMBUATAN observasi yang dijaga try/except, bukan isinya. Kalau
    # blok ini ikut dibungkus, exception dari node akan tertangkap di titik
    # yield, generator melanjutkan, dan Python melempar
    # "generator didn't stop after throw()" — menutupi error yang sebenarnya.
    with cm as s:
        yield s


def usage(resp: Any) -> dict[str, int]:
    """Ambil jumlah token dari respons google-genai, untuk hitungan biaya di Langfuse."""
    u = getattr(resp, "usage_metadata", None)
    if not u:
        return {}
    return {
        "input": getattr(u, "prompt_token_count", 0) or 0,
        "output": getattr(u, "candidates_token_count", 0) or 0,
        "total": getattr(u, "total_token_count", 0) or 0,
    }


class _Rekam:
    """Pembungkus span generation: meneruskan ke Langfuse, sekaligus mencatat token."""

    def __init__(self, span: Any) -> None:
        self._span = span

    def update(self, **kw: Any) -> None:
        catat_token(kw.get("usage_details") or {})
        self._span.update(**kw)


@contextmanager
def generation(nama: str, model: str, masukan: Any) -> Iterator[Any]:
    """Bungkus satu panggilan LLM. Isi `.update(output=..., usage_details=...)` setelahnya.

    Ditandai `generation`, bukan `span`, supaya Langfuse bisa menghitung biaya
    dan membandingkan antar model. Token dicatat lokal juga, karena tabel
    benchmark harus tetap bisa dibuat tanpa Langfuse.
    """
    with _observasi(nama, "generation", model=model, input=masukan) as g:
        yield g if isinstance(g, _Diam) else _Rekam(g)


def _potong(hits: Any, n: int = 8) -> list[str]:
    keluar = []
    for h in (hits or [])[:n]:
        muatan = getattr(h, "payload", None) or {}
        keluar.append(str(muatan.get("chunk_id", "?")))
    return keluar


def _io(nama: str, state: Any, hasil: Any) -> tuple[Any, Any]:
    """Apa yang dilihat dan dihasilkan tiap node.

    Tanpa ini, span-nya cuma batang berwarna dengan durasi. Dengan ini, trace
    bisa menjawab pertanyaan yang sebenarnya: konteks apa yang dipegang sistem
    waktu mengambil keputusan itu.
    """
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


def ukur(nama: str) -> Callable[[F], F]:
    """Bungkus satu node graph: buka span, jalankan, tutup, catat lamanya.

    Node yang gagal tetap ditutup dengan level ERROR — justru node yang gagal
    itu yang paling ingin kamu lihat waktu menelusuri masalah.
    """

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
    """Span akar satu permintaan. Semua span node bersarang di bawahnya."""
    _token.set([])
    with _observasi("tanya-regdocs", "agent", input={"question": pertanyaan}) as s:
        yield s


def tutup(span: Any, pertanyaan: str, state: Mapping[str, Any]) -> None:
    """Isi output dan metadata span akar, lalu kirim."""
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
        # input/output tingkat trace disetel lewat set_trace_io; `update_trace`
        # tidak ada di objek span versi SDK ini
        span.set_trace_io(
            input={"question": pertanyaan},
            output={"answer": str(state.get("answer", ""))[:2000]},
        )
    except Exception as e:  # noqa: BLE001
        print(f"  [trace] gagal menutup trace: {type(e).__name__}: {str(e)[:120]}")


def flush() -> None:
    """Kirim yang tertunda. WAJIB dipanggil SETELAH span akar ditutup.

    Bug nyata Tahap 12: flush dipanggil di dalam blok span akar, jadi span
    itu belum berakhir saat pengiriman jalan — dan tidak pernah terkirim.
    Akibatnya trace muncul tanpa nama dan tanpa metadata, seolah node-nodenya
    melayang tanpa induk.
    """
    if not aktif():
        return
    try:
        _klien().flush()
    except Exception as e:  # noqa: BLE001
        print(f"  [trace] gagal flush: {type(e).__name__}: {str(e)[:120]}")
