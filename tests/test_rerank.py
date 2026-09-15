from qdrant_client.models import ScoredPoint

from app.retrieval.rerank import rerank


def _titik(teks: str, skor: float) -> ScoredPoint:
    return ScoredPoint(id=teks[:8], version=1, score=skor, payload={"text": teks})


def test_yang_relevan_naik_ke_atas() -> None:
    hits = [
        _titik("Tarif pajak penghasilan badan ditetapkan dua puluh dua persen.", 0.9),
        _titik("Bagaimana cara menghapus PB UMKU? Klik ikon keranjang sampah.", 0.8),
        _titik(
            "Kementerian/lembaga, Pemerintah Daerah, Administrator KEK, dan Badan "
            "Pengusahaan KPBPB menerbitkan PB UMKU sesuai kewenangan masing-masing.",
            0.1,
        ),
    ]
    hasil = rerank("Instansi mana yang berwenang menerbitkan PB UMKU?", hits, limit=1)
    assert len(hasil) == 1
    assert "Kementerian/lembaga" in str(hasil[0].payload["text"])


def test_satu_hasil_tidak_perlu_disusun() -> None:
    satu = [_titik("apa saja", 0.5)]
    assert rerank("pertanyaan", satu, limit=5) == satu
    assert rerank("pertanyaan", [], limit=5) == []


def test_skor_ditimpa_skor_cross_encoder() -> None:
    hits = [_titik("Pelaku Usaha wajib memiliki NIB.", 0.99), _titik("Resep rendang.", 0.98)]
    hasil = rerank("kewajiban NIB pelaku usaha", hits, limit=2)
    assert hasil[0].score != 0.99
    assert hasil[0].score > hasil[1].score
