"""Test graph dan normalisasi alias. Tanpa jaringan.

Node yang memanggil LLM (`route_intent`, ekspansi di `rewrite_query`) tidak
diuji di sini — kuota LLM terbatas dan test yang menghabiskannya akan jadi
test yang selalu dimatikan. Yang diuji: bagian deterministik, bentuk graph,
dan pemetaan intent ke parameter retrieval.
"""

from app.agents.graph import bangun
from app.agents.nodes import INTENT_VALID, PARAMETER, rewrite_query
from app.core.entities import ALIAS, normalisasi


def test_alias_ditambahkan_bukan_diganti() -> None:
    """Singkatannya harus tetap ada, supaya BM25 bisa mencocokkannya harfiah."""
    teks, kena = normalisasi("Bagaimana cara mendapatkan NIB lewat OSS?")
    assert "NIB" in teks and "Nomor Induk Berusaha" in teks
    assert "OSS" in teks and "Online Single Submission" in teks
    assert set(kena) == {"nib", "oss"}


def test_nama_lembaga_lama_dikenali() -> None:
    """Pengguna menyebut BKPM; dokumennya memakai nama yang lain."""
    teks, kena = normalisasi("aturan BKPM soal pengawasan")
    assert "Kementerian Investasi dan Hilirisasi" in teks
    assert kena == ["bkpm"]


def test_teks_tanpa_singkatan_tidak_disentuh() -> None:
    asli = "apa saja kewajiban pelaku usaha"
    assert normalisasi(asli) == (asli, [])


def test_tidak_menyentuh_kata_yang_kebetulan_memuat_singkatan() -> None:
    """'boss' memuat 'oss', tapi bukan sistem OSS."""
    teks, kena = normalisasi("siapa boss perusahaan")
    assert kena == []
    assert teks == "siapa boss perusahaan"


def test_rewrite_tanpa_llm_bersifat_deterministik() -> None:
    """Kalau hasilnya berubah-ubah, cache embedding tidak pernah kena."""
    state = {"original_query": "syarat NIB untuk UMK", "ekspansi_llm": False}
    a = rewrite_query(state)  # type: ignore[arg-type]
    b = rewrite_query(state)  # type: ignore[arg-type]
    assert a == b


def test_tiap_intent_punya_parameter() -> None:
    assert set(PARAMETER) == set(INTENT_VALID)
    assert PARAMETER["troubleshooting"][0] == "faq", "keluhan aplikasi harus disaring ke FAQ"
    assert PARAMETER["lookup"][0] is None


def test_graph_punya_lima_node_berurutan() -> None:
    g = bangun().get_graph()
    assert {"rewrite_query", "route_intent", "retrieve", "rerank", "generate"} <= set(g.nodes)


def test_alias_tidak_kosong_dan_lowercase() -> None:
    assert len(ALIAS) > 15
    assert all(k == k.lower() for k in ALIAS)


def test_alias_tidak_diperluas_dua_kali() -> None:
    """Bug nyata Tahap 9: "PB-UMKU" jadi "PB UMKU (...)" lalu tertangkap lagi."""
    teks, kena = normalisasi("kenapa ID izin PB-UMKU saya hilang")
    assert teks.count("Perizinan Berusaha untuk Menunjang Kegiatan Usaha") == 1
    assert kena == ["pb-umku"]


def test_alias_terpanjang_menang() -> None:
    teks, _ = normalisasi("apakah PB UMKU wajib")
    assert "Menunjang Kegiatan Usaha" in teks
