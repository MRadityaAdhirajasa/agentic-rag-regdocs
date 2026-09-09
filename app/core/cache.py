"""Cache embedding di disk, dikunci hash isi teks.

Kenapa ada: satu request embedding tidak bisa diulang gratis. Kuota harian
OpenRouter 50 request, dan korpus penuh memakan 12. Tanpa cache, memperbaiki
satu baris di loader berarti membayar ulang seluruh korpus.

Kenapa hash isi, bukan nama file atau nomor chunk: chunk yang teksnya sama
persis tidak perlu di-embed dua kali, meski datang dari dokumen berbeda. Dan
kalau satu halaman berubah, hanya chunk halaman itu yang jadi cache-miss —
sisanya tetap kena.

Nama model ikut di-hash. Ini bukan detail: mengganti model embedding tanpa
mengganti kunci cache akan mengembalikan vektor dari ruang vektor yang salah,
diam-diam, tanpa error apa pun.

sqlite3 dan array dua-duanya stdlib — cache ini tidak menambah dependensi.
"""

import sqlite3
from array import array
from pathlib import Path

DB_PATH = Path("data/embed_cache.sqlite")

Vector = list[float]


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE IF NOT EXISTS embedding (hash TEXT PRIMARY KEY, vektor BLOB)")
    return conn


class EmbedCache:
    def __init__(self, path: Path = DB_PATH) -> None:
        self.conn = _connect(path)

    def get_many(self, hashes: list[str]) -> dict[str, Vector]:
        out: dict[str, Vector] = {}
        # sqlite membatasi jumlah parameter per query; ambil per potongan
        for start in range(0, len(hashes), 500):
            potongan = hashes[start : start + 500]
            tanya = ",".join("?" * len(potongan))
            for h, blob in self.conn.execute(
                f"SELECT hash, vektor FROM embedding WHERE hash IN ({tanya})", potongan
            ):
                out[h] = array("f", blob).tolist()
        return out

    def put_many(self, pasangan: dict[str, Vector]) -> None:
        """Tulis dan commit sekarang juga.

        Commit per batch inilah yang membuat proses ini tahan Ctrl+C: apa pun
        yang sudah dibayar sudah tersimpan sebelum baris berikutnya jalan.
        """
        self.conn.executemany(
            "INSERT OR REPLACE INTO embedding (hash, vektor) VALUES (?, ?)",
            # float32: presisi yang sama dengan yang disimpan Qdrant, separuh ukuran
            [(h, array("f", v).tobytes()) for h, v in pasangan.items()],
        )
        self.conn.commit()

    def size(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) FROM embedding").fetchone()
        return int(row[0])

    def close(self) -> None:
        self.conn.close()
