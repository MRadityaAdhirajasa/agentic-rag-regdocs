"""PDF -> chunk beridentitas, lewat PyMuPDF.

Tiga hal yang berubah dari Tahap 1:

1. PyMuPDF menggantikan pypdf, dan teks diambil **per halaman**. Karena itu
   tiap chunk tahu ada di halaman berapa — tanpa itu sitasi tidak bisa
   diverifikasi manual, dan verifikasi manual adalah inti tahap ini.
2. Quality gate: dokumen hasil scan tidak punya lapisan teks. Kalau di-ingest
   diam-diam, yang masuk korpus adalah ratusan chunk kosong yang merusak
   metrik di Tahap 4. Lebih baik ditolak keras di depan.
3. Identitas dokumen datang dari `data/metadata.csv`, bukan dari nama file.

Sejak Tahap 5 pemotongan mengikuti batas Pasal (lihat `app/ingestion/pasal.py`).
Kalau struktur pasal tidak terdeteksi, dokumen tetap masuk lewat pemotong
karakter dan ditandai `parse_failed` di payload — kegagalan yang tercatat
lebih berguna daripada dokumen yang diam-diam hilang dari korpus.
"""

import csv
import statistics
from pathlib import Path
from typing import Any

import pymupdf
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.ingestion import pasal

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150
METADATA_CSV = Path("data/metadata.csv")

# Median karakter per halaman. Halaman teks asli di korpus ini ada di kisaran
# 1300-1900; hasil scan mendekati nol karena tidak punya lapisan teks.
MIN_MEDIAN_CHARS = 200

# Lapisan teks beberapa PDF salah membaca huruf kapital I sebagai l — di UU
# 28/2025, 70 dari 95 kata "Izin" tertulis "lzin". Kalimatnya tetap terbaca
# manusia, jadi quality gate berbasis jumlah karakter tidak menangkapnya.
# Dampaknya baru terasa di Tahap 6, saat BM25 mencocokkan kata secara harfiah.
#
# ponytail: daftar eksplisit, bukan koreksi OCR umum. Tambah baris di sini
# kalau ketemu pola baru; kalau daftarnya sudah panjang, ganti PDF sumbernya.
KOREKSI = {
    "lzin": "Izin",
    "Pasa1": "Pasal",
}


def load_metadata(path: Path = METADATA_CSV) -> dict[str, dict[str, str]]:
    if not path.exists():
        raise SystemExit(f"{path} tidak ada. Tahap 2 butuh identitas dokumen, bukan nama file.")
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    kosong = [r["doc_id"] for r in rows if not r.get("status")]
    if kosong:
        print(
            f"PERINGATAN: status masih kosong untuk {', '.join(kosong)}. "
            f"Isi manual setelah cek silang ke peraturan.bpk.go.id — jangan tebak dari tahun."
        )
    return {r["doc_id"]: r for r in rows}


def normalisasi(teks: str) -> tuple[str, int]:
    """Perbaiki salah baca huruf yang sudah terukur. Kembalikan teks dan jumlah perbaikan."""
    jumlah = 0
    for salah, benar in KOREKSI.items():
        n = teks.count(salah)
        if n:
            teks = teks.replace(salah, benar)
            jumlah += n
    return teks, jumlah


def quality_gate(pages: list[str], doc_id: str) -> None:
    median = statistics.median([len(p.strip()) for p in pages]) if pages else 0
    if median < MIN_MEDIAN_CHARS:
        raise SystemExit(
            f"{doc_id} ditolak quality gate: median {median:.0f} karakter/halaman "
            f"(minimum {MIN_MEDIAN_CHARS}). Kemungkinan besar hasil scan tanpa lapisan teks."
        )
    print(f"  quality gate lolos: {len(pages)} halaman, median {median:.0f} karakter/halaman")


def records(meta: dict[str, str]) -> list[dict[str, Any]]:
    """Satu PDF -> daftar record siap embed, tiap record tahu pasal dan halamannya."""
    path = Path(meta["file_path"])
    if not path.exists():
        raise SystemExit(f"File tidak ada: {path} (dari metadata.csv baris {meta['doc_id']})")

    with pymupdf.open(path) as doc:
        mentah = [page.get_text() for page in doc]
    quality_gate(mentah, meta["doc_id"])

    pages, perbaikan = [], 0
    for teks in mentah:
        bersih, n = normalisasi(teks)
        pages.append(bersih)
        perbaikan += n
    if perbaikan:
        print(f"  normalisasi: {perbaikan} salah baca huruf diperbaiki")

    potongan = pasal.pecah(pages)
    if potongan is None:
        print(f"  {meta['doc_id']}: struktur pasal TIDAK terdeteksi, pakai pemotong karakter")
        potongan = _potong_karakter(pages)
        parse_status = "parse_failed"
    else:
        rata = sum(len(p["halaman"]) for p in potongan) / len(potongan)
        print(f"  struktur pasal terdeteksi: {len(potongan)} chunk, {rata:.2f} halaman/chunk")
        parse_status = "ok"

    out: list[dict[str, Any]] = []
    for i, pot in enumerate(potongan):
        halaman = pot["halaman"]
        out.append(
            {
                "text": pot["teks"],
                "payload": {
                    # chunk_id ikut nomor pasal, bukan nomor urut karakter.
                    # Chunk pembukaan dan penjelasan tidak punya nomor pasal;
                    # penanda babnya yang dipakai, bukan "pNone".
                    "chunk_id": (
                        f"{meta['doc_id']}:p{pot['pasal']}:{i}"
                        if pot["pasal"]
                        else f"{meta['doc_id']}:{str(pot['bab'] or 'lain').lower()}:{i}"
                    ),
                    "doc_id": meta["doc_id"],
                    "source_type": "regulasi",
                    "text": pot["teks"],
                    "bab": pot["bab"],
                    "pasal": pot["pasal"],
                    "halaman": halaman[0],
                    "halaman_span": halaman,
                    "parse_status": parse_status,
                    "judul": meta["judul"],
                    "jenis": meta["jenis"],
                    "nomor": meta["nomor"],
                    "tahun": meta["tahun"],
                    "status": meta["status"] or "belum_dicek",
                    "url_sumber": meta["url_sumber"],
                },
            }
        )
    print(f"  {meta['doc_id']}: {len(out)} chunk")
    return out


def _potong_karakter(pages: list[str]) -> list[dict[str, Any]]:
    """Jalur cadangan Tahap 2: potong per halaman, tanpa nomor pasal."""
    pemotong = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    keluar = []
    for nomor_halaman, teks in enumerate(pages, start=1):
        for bagian in pemotong.split_text(teks):
            if bagian.strip():
                keluar.append(
                    {"teks": bagian, "pasal": None, "bab": None, "halaman": [nomor_halaman]}
                )
    return keluar


def all_records(doc_ids: list[str] | None = None) -> list[dict[str, Any]]:
    """Semua dokumen, atau hanya `doc_ids` tertentu.

    Ingest per dokumen penting karena kuota embedding harian terbatas: kalau
    cuma satu dokumen yang berubah, jangan embed ulang seluruh korpus.
    """
    meta = load_metadata()
    if doc_ids:
        tidak_ada = set(doc_ids) - set(meta)
        if tidak_ada:
            raise SystemExit(f"doc_id tidak ada di metadata.csv: {', '.join(sorted(tidak_ada))}")
        meta = {k: v for k, v in meta.items() if k in doc_ids}
    out: list[dict[str, Any]] = []
    for m in meta.values():
        out.extend(records(m))
    return out
