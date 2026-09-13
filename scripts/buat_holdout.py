"""Sisihkan 50 item FAQ untuk uji routing di Tahap 9.

Diambil proporsional dari lima kategori terbesar, dan yang sudah dipakai
sebagai asal pertanyaan golden dibuang — kalau tidak, uji routing dan uji
retrieval memakai item yang sama dan angkanya jadi tidak independen.

Pertanyaan di sini sengaja TIDAK diparafrase: yang diuji keputusan routing,
bukan retrieval.

    uv run python -m scripts.buat_holdout
"""

import json
import random
from pathlib import Path

JUMLAH = 50
BENIH = 28  # tetap, supaya hasilnya sama tiap dijalankan

INTENT = {
    "Manajemen Akun dan Pendaftaran": "troubleshooting",
    "Sistem dan Kendala Teknis": "troubleshooting",
    "Layanan Informasi dan Bantuan Pengguna": "troubleshooting",
    "Proses Perizinan Berusaha": "lookup",
    "Pelaporan, Pelacakan, Pengawasan dan Sanksi": "lookup",
    "Fasilitas, Kemitraan, dan Fitur Pendukung": "lookup",
}


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

    # lima kategori terbesar; yang cuma 3 item tidak cukup untuk disisihkan
    terbesar = sorted(per_kategori, key=lambda k: -len(per_kategori[k]))[:5]
    total = sum(len(per_kategori[k]) for k in terbesar)

    acak = random.Random(BENIH)
    keluar: list[dict[str, str]] = []
    for i, kategori in enumerate(terbesar):
        item = per_kategori[kategori]
        # kategori terakhir menyerap sisa pembulatan
        n = JUMLAH - len(keluar) if i == len(terbesar) - 1 else round(len(item) / total * JUMLAH)
        for it in acak.sample(item, min(n, len(item))):
            keluar.append(
                {
                    "faq_id": it["id"],
                    "question": it["question"],
                    "true_category": kategori,
                    "expected_intent": INTENT[kategori],
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
