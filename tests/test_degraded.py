"""Test tahan banting: budget, dan jalur mundur saat layanan luar mati.

Tanpa jaringan. Kegagalan layanan disimulasikan dengan menukar fungsi yang
memanggilnya — menunggu kuota benar-benar habis bukan cara menguji.
"""

import pytest

from app.agents import nodes
from app.core import budget
from app.core.errors import LayananTidakTersedia


@pytest.fixture(autouse=True)
def _bersih() -> None:  # type: ignore[misc]
    budget.reset()


def test_budget_menghitung_dan_habis(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(budget, "BATAS_HARIAN", 3)
    assert budget.tersisa() == 3
    budget.pakai(2)
    assert budget.tersisa() == 1 and not budget.habis()
    budget.pakai()
    assert budget.habis()


def test_llm_ditolak_saat_budget_habis(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Pagar sendiri harus menahan SEBELUM menabrak kuota penyedia."""
    monkeypatch.setattr(budget, "BATAS_HARIAN", 1)
    budget.pakai()
    with pytest.raises(LayananTidakTersedia, match="budget"):
        nodes._llm("apa pun")


def test_routing_mundur_ke_lookup_saat_llm_mati(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    def mati(_: str) -> str:
        raise LayananTidakTersedia("Gemini", "kuota habis")

    monkeypatch.setattr(nodes, "_llm", mati)
    hasil = nodes.route_intent({"original_query": "kenapa ikon pensil tidak muncul"})  # type: ignore[typeddict-item]
    assert hasil["intent"] == "lookup"
    assert hasil["source_type"] is None, "jangan membuang sumber saat sedang buta"
    assert hasil["degraded_mode"] is True
    assert "routing" in hasil["degraded_reason"][0]


def test_retrieve_turun_ke_sparse_saat_embedding_mati(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    dipanggil = []

    def palsu(kalimat, limit, source_type, rerank, mode="hybrid"):  # type: ignore[no-untyped-def]
        dipanggil.append(mode)
        if mode == "hybrid":
            raise LayananTidakTersedia("OpenRouter", "kuota harian habis")
        return []

    monkeypatch.setattr(nodes, "search", palsu)
    hasil = nodes.retrieve(
        {"top_k": 3, "source_type": None, "rewritten_query": "apa itu NIB", "rerank_aktif": False}  # type: ignore[typeddict-item]
    )
    assert dipanggil == ["hybrid", "sparse"], "harus mencoba hybrid dulu, baru turun"
    assert hasil["degraded_mode"] is True


def test_generate_mengembalikan_kutipan_saat_llm_mati(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Inti Tahap 11: tanpa LLM, pasal yang relevan tetap keluar."""
    from qdrant_client.models import ScoredPoint

    titik = ScoredPoint(
        id="x",
        version=1,
        score=1.0,
        payload={
            "text": "Pelaku Usaha wajib memiliki NIB.",
            "source_type": "regulasi",
            "jenis": "PP",
            "nomor": "28",
            "tahun": "2025",
            "halaman": 12,
            "pasal": "10",
            "status": "berlaku",
        },
    )

    def mati(pertanyaan, hits):  # type: ignore[no-untyped-def]
        raise LayananTidakTersedia("Gemini", "kuota habis")

    monkeypatch.setattr(nodes, "jawab", mati)
    hasil = nodes.generate({"reranked_chunks": [titik], "original_query": "syarat NIB"})  # type: ignore[typeddict-item]

    assert hasil["degraded_mode"] is True
    assert "PP 28/2025" in hasil["answer"], "sitasi harus tetap muncul"
    assert "Pelaku Usaha wajib memiliki NIB" in hasil["answer"]
    assert len(hasil["citations"]) == 1, "sitasi terstruktur tetap dikembalikan"


def test_pagar_budget_dipasang_di_semua_pintu_llm(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Bug nyata Tahap 11: pagar cuma dipasang di routing.

    Akibatnya budget habis tapi jawaban tetap tersusun. Budget yang bocor di
    satu pintu sama saja tidak ada budget.
    """
    from app.agents import verify as v
    from app.core import generate as g

    monkeypatch.setattr(budget, "BATAS_HARIAN", 0)
    for panggil in (
        lambda: nodes._llm("apa pun"),
        lambda: g.jawab("pertanyaan", [object()]),  # type: ignore[list-item]
        lambda: v._nilai("pertanyaan", "jawaban", "konteks"),
    ):
        with pytest.raises(LayananTidakTersedia, match="budget"):
            panggil()
