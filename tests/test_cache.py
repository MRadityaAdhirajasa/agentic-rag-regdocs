"""Test cache dan backoff. Tidak ada jaringan, tidak ada Qdrant, tidak ada API key.

Yang diuji di sini justru bagian yang paling sulit diuji manual: perilaku saat
gagal. Menunggu limit harian benar-benar habis untuk mengetesnya bukan pilihan.
"""

import httpx
import pytest

from app.core import embeddings
from app.core.cache import EmbedCache


def test_cache_bolak_balik(tmp_path) -> None:  # type: ignore[no-untyped-def]
    cache = EmbedCache(tmp_path / "uji.sqlite")
    cache.put_many({"a": [0.1, 0.2, 0.3], "b": [0.4, 0.5, 0.6]})

    hasil = cache.get_many(["a", "b", "tidak-ada"])
    assert set(hasil) == {"a", "b"}
    assert hasil["a"] == pytest.approx([0.1, 0.2, 0.3], abs=1e-6)
    assert cache.size() == 2
    cache.close()


def test_cache_bertahan_setelah_ditutup(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Commit per batch: yang sudah dibayar harus selamat walau proses mati."""
    path = tmp_path / "uji.sqlite"
    cache = EmbedCache(path)
    cache.put_many({"a": [1.0, 2.0]})
    cache.close()

    assert EmbedCache(path).get_many(["a"])["a"] == pytest.approx([1.0, 2.0])


def test_hash_beda_kalau_kind_beda() -> None:
    """`query:` dan `document:` menghasilkan vektor berbeda, jadi kuncinya harus beda."""
    assert embeddings.content_hash("teks", "query") != embeddings.content_hash("teks", "document")


def test_hash_ikut_nama_model(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Ganti model harus jadi cache-miss, bukan memakai vektor dari ruang vektor lain."""
    sebelum = embeddings.content_hash("teks", "query")
    monkeypatch.setattr(embeddings, "EMBED_MODEL", "model/lain")
    assert embeddings.content_hash("teks", "query") != sebelum


def _resp(status: int, body: str) -> httpx.Response:
    return httpx.Response(status, text=body, request=httpx.Request("POST", embeddings.URL))


def test_limit_per_menit_ditunggu() -> None:
    """429 biasa: jeda naik secara eksponensial, dan ada jitter-nya."""
    jeda = [embeddings._jeda_atau_menyerah(_resp(429, "rate limit"), i) for i in range(4)]
    assert jeda[0] < jeda[1] < jeda[2] < jeda[3]
    assert all(j < 40 for j in jeda)


def test_limit_per_hari_langsung_berhenti() -> None:
    """429 harian: menunggu tidak ada gunanya sampai besok, jadi harus berhenti."""
    with pytest.raises(SystemExit, match="harian"):
        embeddings._jeda_atau_menyerah(_resp(429, "free-models-per-day exceeded"), 0)


def test_embed_kosong_tidak_menyentuh_jaringan() -> None:
    assert embeddings.embed([], kind="query") == []


def test_lanjut_dari_titik_terakhir_setelah_mati(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Kriteria penerimaan Tahap 3: mati di tengah, jalan lagi, tidak mengulang dari nol.

    Disimulasikan tanpa jaringan: panggilan ke API diganti stub yang meledak
    di batch kedua, persis seperti Ctrl+C atau kuota habis di tengah jalan.
    """
    monkeypatch.setattr(embeddings, "BATCH", 2)
    db = tmp_path / "c.sqlite"
    monkeypatch.setattr(embeddings, "EmbedCache", lambda: EmbedCache(db))
    monkeypatch.setattr(embeddings, "require", lambda nama, nilai: "kunci-palsu")

    teks = ["satu", "dua", "tiga", "empat"]
    dipanggil: list[int] = []

    def stub(client, key, batch):  # type: ignore[no-untyped-def]
        dipanggil.append(len(batch))
        if len(dipanggil) > 1:
            raise RuntimeError("proses mati di tengah")
        return [[float(i)] * 3 for i in range(len(batch))]

    monkeypatch.setattr(embeddings, "_minta", stub)
    with pytest.raises(RuntimeError, match="mati di tengah"):
        embeddings.embed(teks)

    # batch pertama sudah ter-commit sebelum yang kedua meledak
    assert sum(dipanggil) == 4
    assert EmbedCache(db).size() == 2

    # jalan lagi: hanya sisanya yang diminta, bukan keempatnya
    dipanggil.clear()

    def stub2(client, key, batch):  # type: ignore[no-untyped-def]
        dipanggil.append(len(batch))
        return [[9.0] * 3 for _ in batch]

    monkeypatch.setattr(embeddings, "_minta", stub2)
    hasil = embeddings.embed(teks)
    assert sum(dipanggil) == 2, "yang sudah di cache tidak boleh diminta ulang"
    assert len(hasil) == 4
