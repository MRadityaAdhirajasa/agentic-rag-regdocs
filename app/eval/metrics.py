"""recall@k, MRR, dan nDCG@k. Python murni, tanpa pustaka.

Ditulis sendiri bukan karena tidak ada pustakanya, tapi karena empat rumus
ini yang akan kamu pakai untuk menilai setiap perubahan dari Tahap 5 sampai
13. Kalau isinya kotak hitam, kamu tidak bisa menjelaskan kenapa angkanya
naik atau turun.

Yang dibandingkan adalah **kunci halaman**, bukan chunk_id. chunk_id ikut
berubah setiap cara memotong berubah — dan Tahap 5 memang mengubahnya.
Halaman tetap. Konsekuensinya patokan ini sedikit lebih longgar: satu
halaman berisi sekitar dua chunk, jadi menemukan chunk tetangga di halaman
yang sama tetap dihitung benar.
"""

import math


def recall_at_k(relevan: set[str], terambil: list[str], k: int) -> float:
    """Berapa bagian dari yang seharusnya, berhasil masuk k teratas."""
    if not relevan:
        return 0.0
    kena = relevan & set(terambil[:k])
    return len(kena) / len(relevan)


def mrr(relevan: set[str], terambil: list[str]) -> float:
    """1 dibagi peringkat hasil benar yang pertama. Nol kalau tidak ada sama sekali.

    Peka pada posisi: benar di peringkat 1 bernilai 1.0, di peringkat 5 cuma 0.2.
    Ini yang membedakannya dari recall, yang tidak peduli urutan.
    """
    for i, kunci in enumerate(terambil, start=1):
        if kunci in relevan:
            return 1.0 / i
    return 0.0


def ndcg_at_k(relevan: set[str], terambil: list[str], k: int) -> float:
    """nDCG: seperti MRR tapi menghargai semua hasil benar, bukan cuma yang pertama.

    Hasil benar di peringkat bawah tetap dihitung, dengan bobot yang menyusut
    secara logaritmik. Dibagi dengan susunan ideal supaya rentangnya 0 sampai 1.
    """
    if not relevan:
        return 0.0
    dcg = sum(1 / math.log2(i + 1) for i, k_ in enumerate(terambil[:k], start=1) if k_ in relevan)
    ideal = sum(1 / math.log2(i + 1) for i in range(1, min(len(relevan), k) + 1))
    return dcg / ideal if ideal else 0.0


def ringkas(hasil: list[tuple[set[str], list[str]]]) -> dict[str, float]:
    """Rata-rata semua metrik untuk sekumpulan pertanyaan."""
    if not hasil:
        return {}
    n = len(hasil)
    return {
        "recall@5": sum(recall_at_k(r, t, 5) for r, t in hasil) / n,
        "recall@10": sum(recall_at_k(r, t, 10) for r, t in hasil) / n,
        "mrr": sum(mrr(r, t) for r, t in hasil) / n,
        "ndcg@10": sum(ndcg_at_k(r, t, 10) for r, t in hasil) / n,
        "jumlah_pertanyaan": n,
    }
