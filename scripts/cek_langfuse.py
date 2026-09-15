import sys
import time

from app.core import tracing


def main() -> int:
    print("1. Nilai di .env")
    kurang = []
    for nama, nilai, awalan in (
        ("LANGFUSE_PUBLIC_KEY", tracing.LANGFUSE_PUBLIC, "pk-lf-"),
        ("LANGFUSE_SECRET_KEY", tracing.LANGFUSE_SECRET, "sk-lf-"),
    ):
        if not nilai:
            print(f"   {nama}: KOSONG")
            kurang.append(nama)
        elif not nilai.startswith(awalan):
            print(f"   {nama}: terisi, tapi tidak diawali '{awalan}' — kemungkinan tertukar")
            kurang.append(nama)
        else:
            print(f"   {nama}: {nilai[:12]}... ok")
    print(f"   LANGFUSE_HOST: {tracing.LANGFUSE_HOST}")
    if kurang:
        print("\nIsi dulu di .env, lalu jalankan lagi.")
        return 1

    print("\n2. Key diterima server")
    try:
        klien = tracing._klien()
        if not klien.auth_check():
            print("   DITOLAK. Cek apakah key dan host berasal dari project yang sama.")
            return 1
        print("   diterima.")
    except Exception as e:  # noqa: BLE001
        print(f"   GAGAL: {type(e).__name__}: {str(e)[:200]}")
        return 1

    print("\n3. Kirim satu trace percobaan (bersarang, seperti permintaan sungguhan)")
    pertanyaan = "uji sambungan Langfuse"
    langkah = ("rewrite_query", "retrieve", "generate")
    with tracing.permintaan(pertanyaan) as akar:
        for nama in langkah:
            with tracing._observasi(nama, tracing.TIPE_NODE[nama]) as s:
                s.update(metadata={"ms": 1.0})
        tracing.tutup(
            akar,
            pertanyaan,
            {
                "answer": "Ini trace percobaan dari scripts/cek_langfuse.py.",
                "intent": "lookup",
                "degraded_mode": False,
                "verdict": "tidak_diverifikasi",
                "retry_count": 0,
                "citations": [],
                "trace": [{"node": n, "ms": 1.0} for n in langkah],
            },
        )
    tracing.flush()
    time.sleep(2)
    print("   terkirim.")
    print(f"\nBuka {tracing.LANGFUSE_HOST} -> project kamu -> Tracing.")
    print("Cari trace bernama 'tanya-regdocs'. Kalau belum muncul, tunggu lalu refresh.")
    print("Di dalamnya harus terlihat tiga span bersarang, bukan sejajar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
