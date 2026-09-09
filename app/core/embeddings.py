"""Embedding lewat OpenRouter (format OpenAI-compatible).

Dua hal yang gampang salah dan mahal akibatnya:

1. Nemotron 3 Embed butuh prefix `query: ` untuk pertanyaan dan `document: `
   untuk isi korpus. Tanpa prefix tidak ada error apa pun — recall-nya saja
   yang turun diam-diam. Karena itu prefix dipasang di sini, bukan diserahkan
   ke pemanggil.
2. Free tier OpenRouter dibatasi 50 request/hari. Satu request bisa membawa
   banyak teks sekaligus, jadi batching itu keharusan, bukan optimasi.
"""

import httpx

from app.core.config import EMBED_MODEL, OPENROUTER_API_KEY, require

URL = "https://openrouter.ai/api/v1/embeddings"
BATCH = 128
TIMEOUT = 120.0

Vector = list[float]


def embed(texts: list[str], kind: str = "document") -> list[Vector]:
    """Ubah daftar teks jadi daftar vektor. `kind` = "document" atau "query"."""
    if kind not in ("document", "query"):
        raise ValueError(f"kind harus 'document' atau 'query', bukan {kind!r}")
    key = require("OPENROUTER_API_KEY", OPENROUTER_API_KEY)

    vectors: list[Vector] = []
    with httpx.Client(timeout=TIMEOUT) as client:
        for start in range(0, len(texts), BATCH):
            batch = [f"{kind}: {t}" for t in texts[start : start + BATCH]]
            resp = client.post(
                URL,
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": EMBED_MODEL,
                    "input": batch,
                    # eksplisit: default base64 pernah bikin data balik kosong
                    "encoding_format": "float",
                },
            )
            if resp.status_code != 200:
                raise RuntimeError(f"OpenRouter {resp.status_code}: {resp.text[:500]}")
            data = sorted(resp.json()["data"], key=lambda d: d["index"])
            vectors.extend(d["embedding"] for d in data)

    if len(vectors) != len(texts):
        raise RuntimeError(f"Minta {len(texts)} vektor, dapat {len(vectors)}.")
    return vectors
