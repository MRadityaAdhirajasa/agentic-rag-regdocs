"""Ukur akurasi `route_intent` pada 50 item FAQ yang disisihkan di Tahap 4.

    uv run python -m scripts.eval_routing

Test set ini gratis: tiap item FAQ sudah berlabel kategori sejak diambil dari
OSS, dan kategori itu dipetakan ke intent yang diharapkan. Mengukur akurasi
routing jarang ada di portofolio RAG — kebanyakan berhenti di metrik retrieval.

Peringatan yang harus ikut dilaporkan: pemetaan kategori ke intent itu
buatan kita, bukan label asli. Kategori "Layanan Informasi" misalnya berisi
campuran keluhan aplikasi dan pertanyaan biasa. Karena itu confusion matrix
ikut dicetak — ketidaksepakatan perlu dilihat satu per satu, bukan cuma
dihitung.
"""

import json
import sys
import time
from collections import Counter
from pathlib import Path

from app.agents.nodes import INTENT_VALID, klasifikasi_intent

HOLDOUT = Path("eval/holdout_routing.jsonl")


def main(argv: list[str]) -> None:
    batas = int(argv[argv.index("--batas") + 1]) if "--batas" in argv else 0
    item = [json.loads(b) for b in HOLDOUT.read_text(encoding="utf-8").splitlines() if b.strip()]
    if batas:
        item = item[:batas]
    print(f"{len(item)} item holdout.\n")

    bingung: Counter[tuple[str, str]] = Counter()
    salah = []
    for i, it in enumerate(item, 1):
        try:
            tebakan = klasifikasi_intent(it["question"])
        except Exception as e:  # noqa: BLE001 — satu item gagal tidak boleh membatalkan semua
            print(f"  {it['faq_id']}: GAGAL {type(e).__name__}: {str(e)[:90]}")
            continue
        benar = it["expected_intent"]
        bingung[(benar, tebakan)] += 1
        if tebakan != benar:
            salah.append((it["faq_id"], benar, tebakan, it["question"][:58]))
        if i % 10 == 0:
            print(f"  {i}/{len(item)}")
        time.sleep(0.4)  # jaga jarak dari rate limit Gemini

    total = sum(bingung.values())
    tepat = sum(n for (b, t), n in bingung.items() if b == t)
    print(f"\nAkurasi routing: {tepat}/{total} = {tepat / total:.1%}\n")

    hadir = [i for i in INTENT_VALID if any(i in k for k in bingung)]
    print("Confusion matrix (baris = seharusnya, kolom = tebakan)")
    print(f"{'':<17}" + "".join(f"{t[:9]:>11}" for t in hadir))
    for b in hadir:
        baris = "".join(f"{bingung.get((b, t), 0):>11}" for t in hadir)
        print(f"{b:<17}{baris}")

    if salah:
        print(f"\n{len(salah)} ketidaksepakatan:")
        for fid, benar, tebakan, q in salah:
            print(f"  {fid}  {benar} -> {tebakan}  | {q}")


if __name__ == "__main__":
    main(sys.argv[1:])
