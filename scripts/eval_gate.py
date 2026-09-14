"""Bandingkan hasil evaluasi dengan baseline. Keluar dengan kode 1 kalau turun.

    uv run python -m scripts.eval_gate

Dipakai GitHub Actions untuk memblokir PR yang menurunkan mutu retrieval.
Ambangnya 5 persen relatif, sesuai roadmap.

Baseline CI dipisah dari `eval/baseline.json` dan bukan karena rapi-rapi:
keduanya mengukur hal yang berbeda. Baseline utama memakai hybrid plus
reranking — butuh API key, kuota, dan unduhan model 1,1 GB. Baseline CI
memakai jalur sparse tanpa reranking, yang berjalan tanpa jaringan sama
sekali dan memberi angka sama persis untuk korpus yang sama.

Artinya gate ini **tidak** menjaga mutu sisi dense. Yang dijaganya: pemotongan
dokumen, susunan payload, penulisan ulang pertanyaan, dan pencocokan kata
harfiah. Dari pengalaman sembilan tahap sebelumnya, di situlah kerusakan
paling sering masuk tanpa disadari.
"""

import json
import sys
from pathlib import Path

BASELINE = Path("eval/baseline_ci.json")
AMBANG = 0.05  # turun lebih dari 5 persen relatif = PR diblokir
DIJAGA = ("recall@5", "recall@10", "mrr", "ndcg@10")


def main(argv: list[str]) -> int:
    if "--simpan" in argv:
        return simpan()

    if not BASELINE.exists():
        print(f"{BASELINE} tidak ada. Jalankan dengan --simpan untuk membuatnya.")
        return 1

    lama = json.loads(BASELINE.read_text(encoding="utf-8"))
    baru = ukur()

    if lama["jumlah_pertanyaan"] != baru["jumlah_pertanyaan"]:
        print(
            f"Jumlah pertanyaan berubah {lama['jumlah_pertanyaan']} -> "
            f"{baru['jumlah_pertanyaan']}. Angkanya tidak sebanding; perbarui baseline."
        )
        return 1

    print(f"\n{'metrik':<12}{'baseline':>10}{'sekarang':>10}{'selisih':>10}   status")
    gagal = []
    for m in DIJAGA:
        a, b = lama["metrik"][m], baru[m]
        selisih = b - a
        turun_relatif = (a - b) / a if a else 0.0
        buruk = turun_relatif > AMBANG
        if buruk:
            gagal.append(f"{m}: {a:.3f} -> {b:.3f} (turun {turun_relatif:.1%})")
        print(f"{m:<12}{a:>10.3f}{b:>10.3f}{selisih:>+10.3f}   {'GAGAL' if buruk else 'ok'}")

    if gagal:
        print(f"\nGATE GAGAL — turun lebih dari {AMBANG:.0%}:")
        for g in gagal:
            print(f"  {g}")
        print("\nKalau penurunan ini memang disengaja, perbarui baseline dengan:")
        print("  uv run python -m scripts.eval_gate --simpan")
        return 1

    print(f"\nGATE LOLOS — tidak ada metrik yang turun lebih dari {AMBANG:.0%}.")
    return 0


def ukur() -> dict[str, float]:
    """Jalankan evaluasi pada jalur yang tersedia di CI: sparse, tanpa rerank."""
    import json as _json
    from collections import defaultdict

    from app.eval.metrics import ringkas
    from app.retrieval.search import search_many

    soal = [
        _json.loads(b)
        for b in Path("eval/golden.jsonl").read_text(encoding="utf-8").splitlines()
        if b.strip()
    ]
    # kategori negatif tidak punya jawaban benar; recall-nya selalu nol
    soal = [s for s in soal if s["category"] != "negatif"]
    hasil = search_many([s["question"] for s in soal], limit=10, mode="sparse", rerank=False)
    kel: dict[str, list[tuple[set[str], list[set[str]]]]] = defaultdict(list)
    for s, hits in zip(soal, hasil, strict=True):
        relevan = {f"{p['doc_id']}#h{p['halaman']}" for p in s.get("relevant_pages", [])}
        relevan |= set(s.get("relevant_faq_ids", []))
        terambil = []
        for h in hits:
            p = h.payload or {}
            if p.get("source_type") == "faq":
                terambil.append({str(p["chunk_id"])})
            else:
                span = p.get("halaman_span") or [p["halaman"]]
                terambil.append({f"{p['doc_id']}#h{x}" for x in span})
        kel[s["expected_source_type"]].append((relevan, terambil))
    return ringkas(kel["regulasi"])


def simpan() -> int:
    angka = ukur()
    jumlah = int(angka.pop("jumlah_pertanyaan"))
    BASELINE.write_text(
        json.dumps(
            {
                "catatan": "Jalur CI: sparse-only tanpa rerank, dari eval/korpus_fixture.jsonl.",
                "jumlah_pertanyaan": jumlah,
                "ambang_penurunan": AMBANG,
                "metrik": angka,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Baseline CI disimpan: {angka}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
