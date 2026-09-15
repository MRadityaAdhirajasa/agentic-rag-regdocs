import hashlib
import random
import time

import httpx

from app.core.cache import EmbedCache
from app.core.config import EMBED_MODEL, OPENROUTER_API_KEY, require
from app.core.errors import LayananTidakTersedia

URL = "https://openrouter.ai/api/v1/embeddings"
BATCH = 256
TIMEOUT = 120.0
MAX_PERCOBAAN = 5

Vector = list[float]


def content_hash(text: str, kind: str) -> str:
    return hashlib.sha256(f"{EMBED_MODEL}|{kind}|{text}".encode()).hexdigest()


def _jeda_atau_menyerah(resp: httpx.Response, percobaan: int) -> float:
    if "free-models-per-day" in resp.text:
        raise LayananTidakTersedia(
            "OpenRouter",
            "kuota harian habis (50 request/hari), pulih 00:00 UTC / 07:00 WIB. "
            "Yang sudah ter-embed tersimpan di cache.",
        )
    return float(min(2**percobaan, 30)) + random.uniform(0, 1)


def _minta(client: httpx.Client, key: str, batch: list[str]) -> list[Vector]:
    for percobaan in range(MAX_PERCOBAAN):
        resp = client.post(
            URL,
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": EMBED_MODEL,
                "input": batch,
                "encoding_format": "float",
            },
        )
        if resp.status_code == 200:
            data = sorted(resp.json()["data"], key=lambda d: d["index"])
            return [d["embedding"] for d in data]

        if resp.status_code == 429 or resp.status_code >= 500:
            jeda = _jeda_atau_menyerah(resp, percobaan)
            print(f"  {resp.status_code}, tunggu {jeda:.1f}s (percobaan {percobaan + 1})")
            time.sleep(jeda)
            continue

        if resp.status_code in (401, 403):
            raise LayananTidakTersedia("OpenRouter", f"key ditolak ({resp.status_code})")
        raise RuntimeError(f"OpenRouter {resp.status_code}: {resp.text[:500]}")

    raise LayananTidakTersedia("OpenRouter", f"menyerah setelah {MAX_PERCOBAAN} percobaan")


def embed(texts: list[str], kind: str = "document", pakai_cache: bool = True) -> list[Vector]:
    if kind not in ("document", "query"):
        raise ValueError(f"kind harus 'document' atau 'query', bukan {kind!r}")
    if not texts:
        return []

    hashes = [content_hash(t, kind) for t in texts]
    cache = EmbedCache() if pakai_cache else None
    tersimpan = cache.get_many(list(set(hashes))) if cache else {}

    perlu = [t for t, h in zip(texts, hashes, strict=True) if h not in tersimpan]
    if tersimpan:
        print(f"  cache: {len(texts) - len(perlu)}/{len(texts)} chunk sudah ada")

    if perlu:
        key = require("OPENROUTER_API_KEY", OPENROUTER_API_KEY)
        baru: dict[str, Vector] = {}
        with httpx.Client(timeout=TIMEOUT) as client:
            for start in range(0, len(perlu), BATCH):
                potongan = perlu[start : start + BATCH]
                vektor = _minta(client, key, [f"{kind}: {t}" for t in potongan])
                sebagian = {content_hash(t, kind): v for t, v in zip(potongan, vektor, strict=True)}
                if cache:
                    cache.put_many(sebagian)
                baru.update(sebagian)
                print(f"  embed {min(start + BATCH, len(perlu))}/{len(perlu)}")
        tersimpan.update(baru)

    if cache:
        cache.close()

    hilang = [h for h in hashes if h not in tersimpan]
    if hilang:
        raise RuntimeError(f"{len(hilang)} vektor tidak terisi.")
    return [tersimpan[h] for h in hashes]
