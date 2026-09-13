"""Ukur kualitas retrieval terhadap eval/golden.jsonl.

    uv run python -m scripts.eval
    uv run python -m scripts.eval --mode dense      # bandingkan satu sisi saja
    uv run python -m scripts.eval --tanpa-rerank   # matikan cross-encoder
    uv run python -m scripts.eval --simpan-baseline

Angka dipecah per `expected_source_type`. Ini bukan formalitas: kelompok
`faq` optimistis secara struktural, karena pertanyaannya berasal dari entri
FAQ yang ada di dalam korpus. Menggabungkannya ke satu angka akan menutupi
kualitas sebenarnya di sisi regulasi, dan sisi regulasi itu yang dipakai
jadi gate CI di Tahap 12.
"""

import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from app.eval.metrics import ringkas
from app.retrieval.search import search_many

GOLDEN = Path("eval/golden.jsonl")
BASELINE = Path("eval/baseline.json")
AMBIL = 10  # cukup untuk recall@10; retrieval produksi tetap k=3


def kunci_halaman(doc_id: str, halaman: int | str) -> str:
    return f"{doc_id}#h{halaman}"


def kunci_hasil(payload: dict[str, Any]) -> set[str]:
    """Kunci pembanding satu hasil: himpunan, karena satu chunk bisa lintas halaman.

    Dua jenis sumber punya penanda stabil yang berbeda. FAQ sudah punya id
    sendiri yang tidak berubah; regulasi tidak, jadi dipakai halamannya.
    """
    if payload.get("source_type") == "faq":
        return {str(payload["chunk_id"])}
    doc_id = str(payload["doc_id"])
    span = payload.get("halaman_span") or [payload["halaman"]]
    return {kunci_halaman(doc_id, h) for h in span}


def muat() -> list[dict[str, Any]]:
    if not GOLDEN.exists():
        raise SystemExit(f"{GOLDEN} tidak ada.")
    return [json.loads(b) for b in GOLDEN.read_text(encoding="utf-8").splitlines() if b.strip()]


def tabel(judul: str, angka: dict[str, float]) -> None:
    n = int(angka.pop("jumlah_pertanyaan"))
    print(f"\n{judul}  (n={n})")
    for nama, nilai in angka.items():
        bar = "#" * round(nilai * 30)
        print(f"  {nama:<10} {nilai:.3f}  {bar}")


def main(argv: list[str]) -> None:
    mode = argv[argv.index("--mode") + 1] if "--mode" in argv else "hybrid"
    pakai_rerank = "--tanpa-rerank" not in argv
    soal = muat()
    print(f"{len(soal)} pertanyaan, ambil {AMBIL} teratas. mode={mode} rerank={pakai_rerank}")

    # satu request embedding untuk semua pertanyaan sekaligus
    mulai = time.perf_counter()
    hasil_cari = search_many(
        [s["question"] for s in soal], limit=AMBIL, mode=mode, rerank=pakai_rerank
    )
    lama = (time.perf_counter() - mulai) / len(soal) * 1000
    print(f"rata-rata {lama:.0f} ms per pertanyaan")

    per_kelompok: dict[str, list[tuple[set[str], list[set[str]]]]] = defaultdict(list)
    baris = []
    for s, hits in zip(soal, hasil_cari, strict=True):
        relevan = {kunci_halaman(p["doc_id"], p["halaman"]) for p in s["relevant_pages"]}
        terambil = [kunci_hasil(h.payload) for h in hits if h.payload]
        per_kelompok[s["expected_source_type"]].append((relevan, terambil))
        per_kelompok["SEMUA"].append((relevan, terambil))

        peringkat = next((i for i, h in enumerate(terambil, 1) if h & relevan), None)
        baris.append((s["qid"], peringkat, s["question"][:52]))

    print("\nPeringkat hasil benar pertama per pertanyaan:")
    for qid, peringkat, q in baris:
        tanda = f"#{peringkat}" if peringkat else "TIDAK KETEMU"
        print(f"  {qid}  {tanda:<12} {q}...")

    utama = {}
    for kelompok in ("regulasi", "faq", "SEMUA"):
        if kelompok in per_kelompok:
            angka = ringkas(per_kelompok[kelompok])
            if kelompok == "regulasi":
                utama = dict(angka)
            catatan = "  (optimistis: soal berasal dari korpus)" if kelompok == "faq" else ""
            tabel(f"{kelompok}{catatan}", angka)

    if "--simpan-baseline" in argv:
        BASELINE.write_text(
            json.dumps(
                {
                    "catatan": "Angka utama = expected_source_type regulasi. Patokan halaman.",
                    "tahap": 7,
                    "mode": mode,
                    "rerank": pakai_rerank,
                    "ms_per_pertanyaan": round(lama),
                    "top_k_evaluasi": AMBIL,
                    "metrik_regulasi": utama,
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"\nBaseline disimpan ke {BASELINE}")


if __name__ == "__main__":
    main(sys.argv[1:])
