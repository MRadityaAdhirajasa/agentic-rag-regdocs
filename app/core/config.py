import os

from dotenv import load_dotenv

from app.core.errors import LayananTidakTersedia

load_dotenv()

# Satu-satunya tempat yang membaca .env: modul yang memanggil os.getenv sendiri
# bisa dimuat sebelum baris di atas jalan, dan key-nya terbaca kosong.

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "regdocs")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nvidia/nemotron-3-embed-1b:free")

EMBED_CACHE_PATH = os.getenv("EMBED_CACHE_PATH", "data/embed_cache.sqlite")

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")

LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")
LANGFUSE_HOST = (
    os.getenv("LANGFUSE_BASE_URL") or os.getenv("LANGFUSE_HOST") or "https://cloud.langfuse.com"
)


def require(name: str, value: str) -> str:
    if not value:
        raise LayananTidakTersedia(name, "key kosong di .env")
    return value
