"""Membentuk sitasi dari payload chunk.

Dipisah dari CLI sejak Tahap 8, karena API memberikan sitasi yang sama.
Bentuknya berbeda per jenis sumber, karena yang bisa diverifikasi pembaca
juga berbeda: regulasi bisa dibuka di pasal dan halaman tertentu, FAQ tidak
punya halaman — yang relevan justru kategorinya dan kapan diakses, karena
isinya bisa berubah sewaktu-waktu.
"""

from typing import Any


def citation(payload: dict[str, Any]) -> str:
    if payload.get("source_type") == "faq":
        return f"FAQ OSS — {payload['faq_category']}, diakses {payload['tanggal_akses']}"

    status = payload.get("status", "")
    tanda = "" if status == "berlaku" else f" [status: {status}]"

    # Chunk dari bagian PEMBUKAAN, PENJELASAN, atau dokumen yang gagal
    # diparse tidak punya nomor pasal. Jangan mengarang nomor.
    pasal = payload.get("pasal")
    letak = f"Pasal {pasal}, " if pasal else ""
    if payload.get("bab") in ("PENJELASAN", "PEMBUKAAN"):
        letak = f"{str(payload['bab']).capitalize()}, "

    span = payload.get("halaman_span") or [payload["halaman"]]
    halaman = f"hal. {span[0]}" if len(span) == 1 else f"hal. {span[0]}-{span[-1]}"
    return f"{payload['jenis']} {payload['nomor']}/{payload['tahun']}, {letak}{halaman}{tanda}"
