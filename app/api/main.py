"""HTTP API. Permukaan inilah yang tidak berubah lagi setelah ini.

Alasan API dibangun sebelum graph (Tahap 9): isi dalamnya akan diganti total
jadi LangGraph, dan perubahan sebesar itu jauh lebih aman kalau ada permukaan
tetap untuk membandingkan hasil sebelum dan sesudah. Kontrak di bawah ini
sengaja dikunci sekarang, saat isinya masih sederhana.
"""

import os
import time
from typing import Any

from fastapi import FastAPI, Request
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.agents.graph import tanya
from app.core import budget
from app.core.citation import citation
from app.core.config import QDRANT_COLLECTION
from app.ingestion.faq import FAQ_DIR
from app.ingestion.pdf import load_metadata
from app.retrieval.search import TOP_K

app = FastAPI(
    title="Agentic RAG Regdocs",
    description=(
        "Tanya-jawab atas peraturan perizinan berusaha berbasis risiko, "
        "dengan sitasi tingkat pasal yang bisa diverifikasi."
    ),
    version="0.12.0",
)

# Rate limit per alamat IP. Tanpa ini, satu klien yang mengulang-ulang bisa
# menghabiskan kuota LLM harian untuk semua orang dalam hitungan menit.
BATAS_QUERY = os.getenv("RATE_LIMIT_QUERY", "10/minute")
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
# tanda abaikan tipe: slowapi menuliskan handler-nya untuk RateLimitExceeded,
# sedangkan Starlette mengharapkan Exception yang lebih umum
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]


class Citation(BaseModel):
    citation: str = Field(description="Sitasi siap tampil, mis. 'PP 28/2025, Pasal 136, hal. 81'")
    source_type: str = Field(description="regulasi atau faq")
    doc_id: str
    pasal: str | None = Field(default=None, description="Null untuk FAQ, pembukaan, penjelasan")
    halaman: int | None = Field(default=None, description="Null untuk FAQ")
    question: str | None = Field(default=None, description="Pertanyaan asli, hanya untuk FAQ")
    url_sumber: str | None = None
    score: float = Field(description="Skor cross-encoder. Logit, wajar bernilai negatif")
    text: str = Field(description="Isi potongan yang dipakai menyusun jawaban")


class QueryRequest(BaseModel):
    question: str = Field(min_length=3, description="Pertanyaan dalam Bahasa Indonesia")
    top_k: int = Field(default=TOP_K, ge=1, le=20)
    source_type: str | None = Field(
        default=None,
        description=(
            "Saring ke 'regulasi' atau 'faq' saja. Sejak Tahap 9 routing yang memilih "
            "secara otomatis; bidang ini disimpan untuk kompatibilitas dan diabaikan."
        ),
    )
    rerank: bool = Field(
        default=True,
        description="Penyusunan ulang cross-encoder. Menaikkan mutu, menambah ~4,5 detik",
    )
    verify: bool = Field(
        default=False,
        description=(
            "Nilai jawaban terhadap potongan yang dipakai, dan coba ulang dengan "
            "strategi berbeda kalau tidak didukung. Menambah 1 sampai 5 panggilan LLM"
        ),
    )


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation]
    execution_time_seconds: float
    # Ditambahkan di Tahap 9. Bidang baru bersifat menambah, tidak mengubah
    # yang sudah ada — klien lama tetap jalan.
    intent: str | None = Field(default=None, description="Hasil route_intent")
    rewritten_query: str | None = Field(
        default=None, description="Pertanyaan setelah ditulis ulang"
    )
    # Tahap 10. Terisi hanya kalau verify=true diminta.
    verdict: str | None = Field(
        default=None, description="supported / partial / unsupported / tidak_diverifikasi"
    )
    unsupported_claims: list[str] = Field(default_factory=list)
    supporting_chunk_ids: list[str] = Field(default_factory=list)
    reasoning: str | None = None
    retry_count: int = 0
    strategy_history: list[dict[str, Any]] = Field(
        default_factory=list, description="Parameter yang diubah di tiap percobaan ulang"
    )
    # Tahap 11. True kalau ada layanan luar yang mati dan sistem turun mutu.
    degraded_mode: bool = False
    degraded_reason: list[str] = Field(
        default_factory=list, description="Apa yang mati, dan akibatnya pada jawaban ini"
    )
    # Tahap 12. Lama tiap node, bahan tabel benchmark Tahap 13.
    trace: list[dict[str, Any]] = Field(
        default_factory=list, description="Lama tiap node graph, dalam milidetik"
    )


class DocumentInfo(BaseModel):
    doc_id: str
    judul: str
    jenis: str | None = None
    status: str | None = None
    source_type: str


def _ke_citation(payload: dict[str, Any], score: float) -> Citation:
    return Citation(
        citation=citation(payload),
        source_type=str(payload["source_type"]),
        doc_id=str(payload["doc_id"]),
        pasal=payload.get("pasal"),
        halaman=payload.get("halaman"),
        question=payload.get("question"),
        url_sumber=payload.get("url_sumber") or None,
        score=score,
        text=str(payload["text"]),
    )


@app.get("/health", summary="Cek Qdrant hidup, collection terisi, dan sisa budget")
def health() -> dict[str, Any]:
    from app.ingestion.store import connect

    try:
        jumlah = connect().count(collection_name=QDRANT_COLLECTION).count
    except Exception as e:  # noqa: BLE001 — health check tidak boleh ikut mati
        return {"status": "degraded", "qdrant": f"{type(e).__name__}: {e}"[:200]}
    return {
        "status": "ok" if jumlah else "kosong",
        "collection": QDRANT_COLLECTION,
        "jumlah_titik": jumlah,
        "budget_llm": budget.status(),
    }


@app.get("/documents", response_model=list[DocumentInfo], summary="Sumber yang ada di korpus")
def documents() -> list[DocumentInfo]:
    keluar = [
        DocumentInfo(
            doc_id=doc_id,
            judul=m["judul"],
            jenis=m["jenis"],
            status=m["status"] or None,
            source_type="regulasi",
        )
        for doc_id, m in load_metadata().items()
    ]
    keluar += [
        DocumentInfo(
            doc_id=berkas.stem,
            judul=f"FAQ OSS BKPM — {berkas.stem.replace('_', ' ')}",
            source_type="faq",
        )
        for berkas in sorted(FAQ_DIR.glob("*.json"))
    ]
    return keluar


@app.post("/api/v1/query", response_model=QueryResponse, summary="Tanya korpus")
@limiter.limit(BATAS_QUERY)
def query(request: Request, req: QueryRequest) -> QueryResponse:
    mulai = time.perf_counter()
    state = tanya(req.question, rerank=req.rerank, top_k=req.top_k, verify=req.verify)
    hits = state["reranked_chunks"]
    return QueryResponse(
        answer=state["answer"],
        citations=[_ke_citation(h.payload, h.score) for h in hits if h.payload],
        execution_time_seconds=round(time.perf_counter() - mulai, 3),
        intent=state.get("intent"),
        rewritten_query=state.get("rewritten_query"),
        verdict=state.get("verdict"),
        unsupported_claims=state.get("unsupported_claims", []),
        supporting_chunk_ids=state.get("supporting_chunk_ids", []),
        reasoning=state.get("reasoning"),
        retry_count=state.get("retry_count", 0),
        strategy_history=state.get("strategy_history", []),
        degraded_mode=state.get("degraded_mode", False),
        degraded_reason=state.get("degraded_reason", []),
        trace=state.get("trace", []),
    )
