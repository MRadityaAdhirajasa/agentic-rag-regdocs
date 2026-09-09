"""Satu-satunya tempat yang membaca .env. Modul lain impor dari sini."""

import os

from dotenv import load_dotenv

load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "regdocs")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nvidia/nemotron-3-embed-1b:free")

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")


def require(name: str, value: str) -> str:
    """Gagal keras dan jelas kalau key belum diisi, bukan 401 misterius dari server."""
    if not value:
        raise RuntimeError(f"{name} kosong. Isi di file .env lalu jalankan lagi.")
    return value
