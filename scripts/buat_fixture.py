"""Bekukan korpus jadi satu berkas yang muat di repo, untuk gate CI.

    uv run python -m scripts.buat_fixture

Kenapa perlu: PDF sumber tidak masuk repo (tertahan `*.pdf`), dan cache
embedding 29 MB juga tidak. Tanpa fixture, komputer CI tidak punya apa pun
untuk dicari — gate-nya jadi mustahil.

Yang dibekukan hanya **teks dan payload**, bukan vektor. Vektor dense butuh
API dan kuota; vektor sparse (BM25) dihitung ulang di CI dalam hitungan detik
tanpa jaringan. Itu yang membuat gate ini deterministik dan gratis.
"""

import json
from pathlib import Path

from app.ingestion import faq, pdf

TUJUAN = Path("eval/korpus_fixture.jsonl")


def main() -> None:
    records = pdf.all_records() + faq.records()
    baris = [
        json.dumps({"text": r["text"], "payload": r["payload"]}, ensure_ascii=False)
        for r in records
    ]
    TUJUAN.write_text("\n".join(baris) + "\n", encoding="utf-8")
    ukuran = TUJUAN.stat().st_size / 1_000_000
    print(f"\n{len(records)} chunk -> {TUJUAN} ({ukuran:.1f} MB)")


if __name__ == "__main__":
    main()
