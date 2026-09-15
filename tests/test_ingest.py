import json
from pathlib import Path

import pytest

from app.ingestion import faq, pdf

FAQ_DIR = Path("dokumen/faq")


def test_quality_gate_menolak_hasil_scan() -> None:
    with pytest.raises(SystemExit, match="quality gate"):
        pdf.quality_gate(["", "  ", "\n"], "dokumen-scan")


def test_quality_gate_meloloskan_teks_asli() -> None:
    pdf.quality_gate(["x" * 1500] * 5, "dokumen-teks")


def test_metadata_punya_kolom_wajib() -> None:
    meta = pdf.load_metadata()
    assert meta, "metadata.csv kosong"
    for doc_id, row in meta.items():
        for kolom in ("judul", "jenis", "nomor", "tahun", "file_path"):
            assert row[kolom], f"{doc_id} kolom {kolom} kosong"


@pytest.mark.skipif(not FAQ_DIR.exists(), reason="folder FAQ tidak ada")
def test_faq_embed_gabungan_question_dan_answer() -> None:
    records = faq.records(FAQ_DIR)
    assert len(records) > 300

    contoh = records[0]
    berkas = sorted(FAQ_DIR.glob("*.json"))[0]
    item = json.loads(berkas.read_text(encoding="utf-8"))["items"][0]

    assert contoh["text"].startswith(item["question"])
    assert item["answer"] in contoh["text"]
    assert contoh["payload"]["source_type"] == "faq"
    assert "notes" not in contoh["payload"]


def test_normalisasi_memperbaiki_salah_baca_huruf() -> None:
    teks, jumlah = pdf.normalisasi("wajib memenuhi persyaratan lzin sesuai Pasa1 227")
    assert teks == "wajib memenuhi persyaratan Izin sesuai Pasal 227"
    assert jumlah == 2


def test_normalisasi_tidak_menyentuh_teks_bersih() -> None:
    bersih = "Pelaku Usaha wajib memiliki Izin sesuai Pasal 227"
    assert pdf.normalisasi(bersih) == (bersih, 0)
