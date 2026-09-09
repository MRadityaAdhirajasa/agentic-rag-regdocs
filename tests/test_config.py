"""Test yang tidak butuh Qdrant, supaya CI bisa jalan tanpa service."""

import os

from dotenv import load_dotenv

load_dotenv()


def test_qdrant_url_terbaca() -> None:
    url = os.getenv("QDRANT_URL", "http://localhost:6333")
    assert url.startswith("http")


def test_collection_name_ada() -> None:
    name = os.getenv("QDRANT_COLLECTION", "regdocs")
    assert len(name) > 0
