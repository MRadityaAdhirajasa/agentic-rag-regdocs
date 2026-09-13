"""Test API. Sengaja hanya yang bisa jalan tanpa Qdrant dan tanpa API key.

`/api/v1/query` butuh keduanya, jadi tidak diuji di sini — test yang butuh
layanan luar akan jadi test yang selalu dimatikan orang. Yang diuji: kontrak
responsnya, dan bahwa `/health` tetap menjawab saat Qdrant mati.
"""

from fastapi.testclient import TestClient

from app.api.main import QueryRequest, app

client = TestClient(app)


def test_health_tidak_ikut_mati_saat_qdrant_mati() -> None:
    """Health check yang ikut melempar error tidak ada gunanya."""
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] in ("ok", "kosong", "degraded")


def test_documents_menyebut_kedua_jenis_sumber() -> None:
    r = client.get("/documents")
    assert r.status_code == 200
    isi = r.json()
    jenis = {d["source_type"] for d in isi}
    assert jenis == {"regulasi", "faq"}
    regulasi = next(d for d in isi if d["source_type"] == "regulasi")
    # identitas diambil dari metadata.csv, bukan dari nama berkas PDF
    assert regulasi["jenis"] == "PP"


def test_pertanyaan_terlalu_pendek_ditolak() -> None:
    """Validasi di batas kepercayaan, bukan di dalam."""
    assert client.post("/api/v1/query", json={"question": "a"}).status_code == 422
    assert client.post("/api/v1/query", json={}).status_code == 422


def test_top_k_dibatasi() -> None:
    assert (
        client.post("/api/v1/query", json={"question": "apa itu NIB", "top_k": 999}).status_code
        == 422
    )


def test_bawaan_permintaan() -> None:
    """Kontrak yang dikunci Tahap 8: bawaan tidak boleh berubah diam-diam."""
    req = QueryRequest(question="apa itu NIB")
    assert req.rerank is True
    assert req.source_type is None


def test_openapi_punya_tiga_endpoint() -> None:
    jalur = client.get("/openapi.json").json()["paths"]
    assert set(jalur) == {"/health", "/documents", "/api/v1/query"}
