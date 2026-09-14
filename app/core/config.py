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


def require(name: str, value: str) -> str:
    """Gagal keras dan jelas kalau key belum diisi, bukan 401 misterius dari server.

    Sejak Tahap 11 jenis error-nya khusus, supaya pemanggil bisa memilih
    menurunkan mutu layanan alih-alih mati.
    """
    if not value:
        raise LayananTidakTersedia(name, "key kosong di .env")
    return value
