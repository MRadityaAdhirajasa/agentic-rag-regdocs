"""Catat berapa lama tiap node berjalan, lalu kirim ke Langfuse kalau disetel.

Dua sasaran, dan yang pertama lebih penting daripada yang kedua:

1. **Angka latensi per node** ikut terbawa di respons API. Inilah bahan tabel
   benchmark Tahap 13 — p50, p95, dan perbandingan verify on/off. Tanpa ini,
   Tahap 13 harus mengukur ulang dari nol.
2. **Langfuse** sebagai tempat menumpuknya trace dari banyak permintaan.
   Opsional: tanpa `LANGFUSE_PUBLIC_KEY` dan `LANGFUSE_SECRET_KEY`, seluruh
   modul ini diam dan tidak menambah satu milidetik pun.

Sengaja tidak memakai callback handler LangChain. Yang kita ukur node graph
sendiri, dan membungkusnya langsung membuat angka yang muncul persis angka
yang kita maksud — bukan apa pun yang kebetulan dilaporkan pustaka.
"""

import os
import time
from collections.abc import Callable, Mapping
from functools import lru_cache, wraps
from typing import Any, TypeVar, cast

LANGFUSE_PUBLIC = os.getenv("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET = os.getenv("LANGFUSE_SECRET_KEY", "")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

# TypeVar supaya tipe node tetap utuh setelah dibungkus — LangGraph
# memeriksa tanda tangan node-nya, jadi Callable[[Any], Any] ditolak.
F = TypeVar("F", bound=Callable[..., Any])


def aktif() -> bool:
    return bool(LANGFUSE_PUBLIC and LANGFUSE_SECRET)


@lru_cache(maxsize=1)
def _klien() -> Any:
    from langfuse import Langfuse

    return Langfuse(public_key=LANGFUSE_PUBLIC, secret_key=LANGFUSE_SECRET, host=LANGFUSE_HOST)


def ukur(nama: str) -> Callable[[F], F]:
    """Bungkus satu node graph supaya lamanya tercatat di state.

    Node yang gagal tetap dicatat — justru node yang gagal itu yang paling
    ingin kamu lihat waktu menelusuri masalah.
    """

    def bungkus(fn: F) -> F:
        @wraps(fn)
        def jalan(state: Any) -> Any:
            mulai = time.perf_counter()
            try:
                hasil = fn(state)
            except Exception:
                lama = (time.perf_counter() - mulai) * 1000
                # dicatat lewat state pemanggil tidak mungkin di sini, jadi
                # dicetak; yang penting jejaknya tidak hilang diam-diam
                print(f"  [trace] {nama} gagal setelah {lama:.0f} ms")
                raise
            lama = (time.perf_counter() - mulai) * 1000
            return {**hasil, "trace": [{"node": nama, "ms": round(lama, 1)}]}

        return cast(F, jalan)

    return bungkus


def kirim(pertanyaan: str, state: Mapping[str, Any]) -> None:
    """Kirim satu permintaan sebagai trace ke Langfuse. Diam kalau tidak disetel."""
    if not aktif():
        return
    try:
        klien = _klien()
        total = sum(t["ms"] for t in state.get("trace", []))
        induk = klien.start_observation(
            name="tanya",
            as_type="chain",
            input={"question": pertanyaan},
            output={"answer": state.get("answer", "")[:2000]},
            metadata={
                "intent": state.get("intent"),
                "degraded_mode": state.get("degraded_mode", False),
                "verdict": state.get("verdict"),
                "retry_count": state.get("retry_count", 0),
                "total_ms": round(total, 1),
                "jumlah_sitasi": len(state.get("citations", [])),
            },
        )
        for langkah in state.get("trace", []):
            anak = klien.start_observation(
                name=langkah["node"], as_type="span", metadata={"ms": langkah["ms"]}
            )
            anak.end()
        induk.end()
        klien.flush()
    except Exception as e:  # noqa: BLE001
        # Pemantauan yang menjatuhkan permintaan adalah pemantauan yang salah.
        print(f"  [trace] gagal kirim ke Langfuse: {type(e).__name__}: {str(e)[:120]}")
