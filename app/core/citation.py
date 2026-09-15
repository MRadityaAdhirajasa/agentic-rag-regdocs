from typing import Any


def citation(payload: dict[str, Any]) -> str:
    if payload.get("source_type") == "faq":
        return f"FAQ OSS — {payload['faq_category']}, diakses {payload['tanggal_akses']}"

    status = payload.get("status", "")
    tanda = "" if status == "berlaku" else f" [status: {status}]"

    pasal = payload.get("pasal")
    letak = f"Pasal {pasal}, " if pasal else ""
    if payload.get("bab") in ("PENJELASAN", "PEMBUKAAN"):
        letak = f"{str(payload['bab']).capitalize()}, "

    span = payload.get("halaman_span") or [payload["halaman"]]
    halaman = f"hal. {span[0]}" if len(span) == 1 else f"hal. {span[0]}-{span[-1]}"
    return f"{payload['jenis']} {payload['nomor']}/{payload['tahun']}, {letak}{halaman}{tanda}"
