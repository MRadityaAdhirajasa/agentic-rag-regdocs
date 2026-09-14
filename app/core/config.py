"""Satu-satunya tempat yang membaca .env. Modul lain impor dari sini."""

import os

from dotenv import load_dotenv

from app.core.errors import LayananTidakTersedia

load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "regdocs")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nvidia/nemotron-3-embed-1b:free")

EMBED_CACHE_PATH = os.getenv("EMBED_CACHE_PATH", "data/embed_cache.sqlite")

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")

# Pemantauan (opsional). Dibaca di sini, bukan di app/core/tracing.py, karena
# modul mana pun yang membaca os.getenv di tingkat modulnya sendiri bisa
# dimuat SEBELUM load_dotenv() di atas sempat jalan — dan hasilnya key
# terbaca kosong padahal .env-nya benar.
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")
# Dokumentasi Langfuse memakai LANGFUSE_BASE_URL; SDK-nya menerima keduanya.
# Yang baru didahulukan, yang lama tetap diterima supaya .env lama tidak rusak.
LANGFUSE_HOST = (
    os.getenv("LANGFUSE_BASE_URL") or os.getenv("LANGFUSE_HOST") or "https://cloud.langfuse.com"
)


def require(name: str, value: str) -> str:
    """Gagal keras dan jelas kalau key belum diisi, bukan 401 misterius dari server.

    Sejak Tahap 11 jenis error-nya khusus, supaya pemanggil bisa memilih
    menurunkan mutu layanan alih-alih mati.
    """
    if not value:
        raise LayananTidakTersedia(name, "key kosong di .env")
    return value
