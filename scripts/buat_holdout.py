import json
import random
from pathlib import Path

JUMLAH = 50
BENIH = 28

KATA_ANTARMUKA = [
    "klik",
    "menu ",
    "tautan",
    "https://",
    "pilih ",
    "tombol",
    "ikon",
    "panduan",
    "laman",
    "kolom",
    "unggah",
]
AMBANG_ANTARMUKA = 2


def intent_dari_jawaban(answer: str) -> str:
    skor = sum(answer.lower().count(k) for k in KATA_ANTARMUKA)
    return "troubleshooting" if skor >= AMBANG_ANTARMUKA else "lookup"


def main() -> None:
    dipakai = {
        json.loads(b)["origin"]["faq_id"]
        for b in Path("eval/golden.jsonl").read_text(encoding="utf-8").splitlines()
        if b.strip()
    }
    dipakai.discard(None)

    per_kategori: dict[str, list[dict[str, str]]] = {}
    for berkas in sorted(Path("dokumen/faq").glob("*.json")):
        data = json.loads(berkas.read_text(encoding="utf-8"))
        kategori = data["source"]["category"]
        per_kategori[kategori] = [i for i in data["items"] if i["id"] not in dipakai]

    terbesar = sorted(per_kategori, key=lambda k: -len(per_kategori[k]))[:5]
    total = sum(len(per_kategori[k]) for k in terbesar)

    acak = random.Random(BENIH)
    keluar: list[dict[str, str]] = []
    for i, kategori in enumerate(terbesar):
        item = per_kategori[kategori]
        n = JUMLAH - len(keluar) if i == len(terbesar) - 1 else round(len(item) / total * JUMLAH)
        for it in acak.sample(item, min(n, len(item))):
            keluar.append(
                {
                    "faq_id": it["id"],
                    "question": it["question"],
                    "true_category": kategori,
                    "expected_intent": intent_dari_jawaban(it["answer"]),
                    "expected_source_type": "faq",
                }
            )
        print(f"  {kategori}: {n}")

    Path("eval/holdout_routing.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in keluar) + "\n", encoding="utf-8"
    )
    print(f"{len(keluar)} item ditulis ke eval/holdout_routing.jsonl")


if __name__ == "__main__":
    main()
