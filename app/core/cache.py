import sqlite3
from array import array
from pathlib import Path

from app.core.config import EMBED_CACHE_PATH

DB_PATH = Path(EMBED_CACHE_PATH)

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
        for start in range(0, len(hashes), 500):
            potongan = hashes[start : start + 500]
            tanya = ",".join("?" * len(potongan))
            for h, blob in self.conn.execute(
                f"SELECT hash, vektor FROM embedding WHERE hash IN ({tanya})", potongan
            ):
                out[h] = array("f", blob).tolist()
        return out

    def put_many(self, pasangan: dict[str, Vector]) -> None:
        self.conn.executemany(
            "INSERT OR REPLACE INTO embedding (hash, vektor) VALUES (?, ?)",
            [(h, array("f", v).tobytes()) for h, v in pasangan.items()],
        )
        self.conn.commit()

    def size(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) FROM embedding").fetchone()
        return int(row[0])

    def close(self) -> None:
        self.conn.close()
