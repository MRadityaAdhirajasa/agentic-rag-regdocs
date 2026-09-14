"""Jaga agar korpus beku untuk CI tidak basi.

Gate CI memakai `eval/korpus_fixture.jsonl`, bukan PDF — PDF tidak masuk repo.
Akibatnya perubahan pada pemotong dokumen **tidak** terlihat oleh gate sampai
fixture-nya dibuat ulang. Test inilah yang menutup celah itu.

Hanya jalan di mesin yang punya PDF sumbernya. Di CI dia dilewati, dan memang
harus begitu: di sana tidak ada yang bisa dibandingkan.
"""

import json
from pathlib import Path

import pytest

FIXTURE = Path("eval/korpus_fixture.jsonl")


def _punya_pdf() -> bool:
    from app.ingestion.pdf import METADATA_CSV

    if not METADATA_CSV.exists():
        return False
    import csv

    with METADATA_CSV.open(encoding="utf-8", newline="") as f:
        return all(Path(r["file_path"]).exists() for r in csv.DictReader(f))


@pytest.mark.skipif(not _punya_pdf(), reason="PDF sumber tidak ada (wajar di CI)")
def test_fixture_masih_cocok_dengan_pemotong() -> None:
    """Kalau gagal: jalankan `make fixture` lalu `make eval-gate -- --simpan`."""
    from app.ingestion import faq, pdf

    sekarang = pdf.all_records() + faq.records()
    beku = [json.loads(b) for b in FIXTURE.read_text(encoding="utf-8").splitlines() if b.strip()]

    assert len(beku) == len(sekarang), (
        f"fixture punya {len(beku)} chunk, pemotong sekarang menghasilkan "
        f"{len(sekarang)}. Fixture basi — jalankan `make fixture`."
    )
    id_beku = [b["payload"]["chunk_id"] for b in beku]
    id_baru = [r["payload"]["chunk_id"] for r in sekarang]
    assert id_beku == id_baru, "chunk_id berubah; fixture basi — jalankan `make fixture`."
