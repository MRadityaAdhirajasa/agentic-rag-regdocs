import pytest

from app.agents.verify import MAX_RETRIES, cukup_atau_ulangi, mutate_strategy, verify


def test_penolakan_dikenali_tanpa_memanggil_llm() -> None:
    hasil = verify(
        {"verify_aktif": True, "answer": "Tidak tahu.", "reranked_chunks": []}  # type: ignore[typeddict-item]
    )
    assert hasil["verdict"] == "unsupported"
    assert "tidak tahu" in hasil["reasoning"].lower()


def test_verifikasi_mati_kalau_tidak_diminta() -> None:
    hasil = verify({"verify_aktif": False})  # type: ignore[typeddict-item]
    assert hasil["verdict"] == "tidak_diverifikasi"


def test_berhenti_saat_didukung() -> None:
    assert cukup_atau_ulangi({"verify_aktif": True, "verdict": "supported"}) == "selesai"  # type: ignore[typeddict-item]
    assert cukup_atau_ulangi({"verify_aktif": True, "verdict": "partial"}) == "selesai"  # type: ignore[typeddict-item]


def test_mengulang_saat_tidak_didukung() -> None:
    state = {"verify_aktif": True, "verdict": "unsupported", "retry_count": 0}
    assert cukup_atau_ulangi(state) == "ulangi"  # type: ignore[arg-type]


def test_berhenti_setelah_batas_percobaan() -> None:
    state = {"verify_aktif": True, "verdict": "unsupported", "retry_count": MAX_RETRIES}
    assert cukup_atau_ulangi(state) == "selesai"  # type: ignore[arg-type]


def test_verifikasi_gagal_tidak_memicu_pengulangan() -> None:
    state = {"verify_aktif": True, "verdict": "gagal_diverifikasi", "retry_count": 0}
    assert cukup_atau_ulangi(state) == "selesai"  # type: ignore[arg-type]


def test_tiap_percobaan_mengubah_parameter() -> None:
    state = {
        "original_query": "pertanyaan asli",
        "rewritten_query": "pertanyaan asli yang diperluas",
        "top_k": 3,
        "source_type": "faq",
        "retry_count": 0,
    }
    satu = mutate_strategy(state)  # type: ignore[arg-type]
    assert satu["top_k"] > 3
    assert satu["source_type"] is None
    assert satu["retry_count"] == 1

    state.update(satu)  # type: ignore[arg-type]
    dua = mutate_strategy(state)  # type: ignore[arg-type]
    assert dua["query_dipakai"] == "pertanyaan asli", "percobaan 2 harus kembali ke pertanyaan asli"
    assert dua["retry_count"] == 2
    assert len(dua["strategy_history"]) == 2


def test_mutasi_yang_tidak_mengubah_apa_pun_ditolak() -> None:
    state = {
        "original_query": "sama",
        "rewritten_query": "sama",
        "top_k": 8,
        "source_type": None,
        "query_dipakai": "sama",
        "retry_count": 1,
    }
    with pytest.raises(RuntimeError, match="tidak mengubah"):
        mutate_strategy(state)  # type: ignore[arg-type]
