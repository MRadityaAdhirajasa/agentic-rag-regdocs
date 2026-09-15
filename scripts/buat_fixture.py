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
