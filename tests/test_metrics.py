"""Test metrik dengan angka yang bisa dihitung tangan.

Rumus evaluasi yang salah jauh lebih berbahaya daripada retrieval yang
salah: dia bikin kamu percaya perubahan yang merugikan itu menguntungkan.
"""

import math

from app.eval.metrics import mrr, ndcg_at_k, recall_at_k, ringkas


def test_recall_setengah() -> None:
    assert recall_at_k({"a", "b"}, [{"a"}, {"x"}, {"y"}], 5) == 0.5


def test_recall_hormati_batas_k() -> None:
    """Yang benar tapi ada di peringkat 6 tidak boleh dihitung di recall@5."""
    assert recall_at_k({"a"}, [{"x"}] * 5 + [{"a"}], 5) == 0.0
    assert recall_at_k({"a"}, [{"x"}] * 5 + [{"a"}], 10) == 1.0


def test_mrr_peka_peringkat() -> None:
    assert mrr({"a"}, [{"a"}, {"b"}]) == 1.0
    assert mrr({"a"}, [{"b"}, {"a"}]) == 0.5
    assert mrr({"a"}, [{"b"}, {"c"}]) == 0.0


def test_ndcg_sempurna_bernilai_satu() -> None:
    assert ndcg_at_k({"a", "b"}, [{"a"}, {"b"}, {"c"}], 10) == 1.0


def test_chunk_lintas_halaman_dihitung_sekali_saja() -> None:
    """Satu chunk yang mencakup dua halaman benar, menutup keduanya."""
    assert recall_at_k({"h50", "h51"}, [{"h50", "h51"}], 5) == 1.0
    assert recall_at_k({"h50", "h51"}, [{"h50"}], 5) == 0.5


def test_ndcg_urutan_terbalik_lebih_kecil() -> None:
    bagus = ndcg_at_k({"a"}, [{"a"}, {"x"}, {"x"}], 10)
    jelek = ndcg_at_k({"a"}, [{"x"}, {"x"}, {"a"}], 10)
    assert bagus > jelek
    assert math.isclose(jelek, (1 / math.log2(4)) / 1.0)


def test_relevan_kosong_tidak_meledak() -> None:
    assert recall_at_k(set(), [{"a"}], 5) == 0.0
    assert ndcg_at_k(set(), [{"a"}], 5) == 0.0


def test_ringkas_menghitung_jumlah() -> None:
    r = ringkas([({"a"}, [{"a"}]), ({"b"}, [{"x"}])])
    assert r["jumlah_pertanyaan"] == 2
    assert r["recall@5"] == 0.5
