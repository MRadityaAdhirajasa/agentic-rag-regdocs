"""Embedding lewat OpenRouter (format OpenAI-compatible), dengan cache dan backoff.

Tiga hal yang gampang salah dan mahal akibatnya:

1. Nemotron 3 Embed butuh prefix `query: ` untuk pertanyaan dan `document: `
   untuk isi korpus. Tanpa prefix tidak ada error apa pun — recall-nya saja
   yang turun diam-diam. Karena itu prefix dipasang di sini, bukan diserahkan
   ke pemanggil.
2. Free tier OpenRouter dibatasi 50 request/hari dan 20 request/menit. Satu
   request menampung maksimum 256 teks, jadi batching itu keharusan, bukan
   optimasi. Korpus 2900 chunk jadi 12 request, bukan 2900.
3. Dua limit itu butuh perlakuan berbeda, dan menyamakannya adalah kesalahan
   yang mahal — lihat `_jeda_atau_menyerah`.
"""

import hashlib
import random
import time

import httpx

from app.core.cache import EmbedCache
from app.core.config import EMBED_MODEL, OPENROUTER_API_KEY, require

URL = "https://openrouter.ai/api/v1/embeddings"
BATCH = 256  # batas keras server OpenRouter; 512 ditolak 400
TIMEOUT = 120.0
MAX_PERCOBAAN = 5

Vector = list[float]


def content_hash(text: str, kind: str) -> str:
    """Kunci cache. Nama model ikut supaya ganti model = cache-miss, bukan vektor salah."""
    return hashlib.sha256(f"{EMBED_MODEL}|{kind}|{text}".encode()).hexdigest()


def _jeda_atau_menyerah(resp: httpx.Response, percobaan: int) -> float:
    """Tentukan berapa lama menunggu, atau berhenti sama sekali.

    Limit per-menit lewat sendirinya dalam hitungan detik — itu layak ditunggu.
    Limit per-hari baru pulih besok pagi; menunggunya berarti proses menggantung
    berjam-jam sambil pura-pura bekerja. Lebih jujur berhenti dan bilang kenapa.
    """
    if "free-models-per-day" in resp.text:
        raise SystemExit(
            "Kuota embedding harian OpenRouter habis (50 request/hari).\n"
            "Pulih pada 00:00 UTC (07:00 WIB). Yang sudah ter-embed tersimpan "
            "di cache, jadi menjalankan ulang nanti tidak mengulang dari nol."
        )
    # eksponensial plus jitter: tanpa jitter, beberapa proses yang kena limit
    # bersamaan akan mencoba lagi pada detik yang sama persis, dan bertabrakan lagi
    return float(min(2**percobaan, 30)) + random.uniform(0, 1)


def _minta(client: httpx.Client, key: str, batch: list[str]) -> list[Vector]:
    for percobaan in range(MAX_PERCOBAAN):
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
        if resp.status_code == 200:
            data = sorted(resp.json()["data"], key=lambda d: d["index"])
            return [d["embedding"] for d in data]

        if resp.status_code == 429 or resp.status_code >= 500:
            jeda = _jeda_atau_menyerah(resp, percobaan)
            print(f"  {resp.status_code}, tunggu {jeda:.1f}s (percobaan {percobaan + 1})")
            time.sleep(jeda)
            continue

        raise RuntimeError(f"OpenRouter {resp.status_code}: {resp.text[:500]}")

    raise RuntimeError(f"Menyerah setelah {MAX_PERCOBAAN} percobaan.")


def embed(texts: list[str], kind: str = "document", pakai_cache: bool = True) -> list[Vector]:
    """Ubah daftar teks jadi daftar vektor. `kind` = "document" atau "query"."""
    if kind not in ("document", "query"):
        raise ValueError(f"kind harus 'document' atau 'query', bukan {kind!r}")
    if not texts:
        return []

    hashes = [content_hash(t, kind) for t in texts]
    cache = EmbedCache() if pakai_cache else None
    tersimpan = cache.get_many(list(set(hashes))) if cache else {}

    # urutan asli dipertahankan; yang belum ada saja yang dibayar
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
                    # ditulis per batch, bukan di akhir: inilah checkpoint-nya
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
