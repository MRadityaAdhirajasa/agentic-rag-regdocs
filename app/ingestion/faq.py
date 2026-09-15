import json
from pathlib import Path
from typing import Any

FAQ_DIR = Path("dokumen/faq")


def records(directory: Path = FAQ_DIR) -> list[dict[str, Any]]:
    files = sorted(directory.glob("*.json"))
    if not files:
        raise SystemExit(f"Tidak ada file JSON di {directory}.")

    out: list[dict[str, Any]] = []
    terlihat: set[str] = set()
    kembar = 0
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        sumber = data["source"]
        kategori = sumber["category"]
        items = data["items"]
        for item in items:
            teks = f"{item['question']}\n\n{item['answer']}"
            if teks in terlihat:
                kembar += 1
                continue
            terlihat.add(teks)
            out.append(
                {
                    "text": teks,
                    "payload": {
                        "chunk_id": item["id"],
                        "doc_id": path.stem,
                        "source_type": "faq",
                        "text": teks,
                        "question": item["question"],
                        "faq_category": kategori,
                        "confidence": item.get("confidence", ""),
                        "url_sumber": item.get("reference_url", ""),
                        "tanggal_akses": sumber.get("last_updated", ""),
                    },
                }
            )
        print(f"  {path.name}: {len(items)} item — {kategori}")
    if kembar:
        print(f"  {kembar} item kembar dibuang")
    if kembar:
        print(f"  {kembar} item kembar dibuang")
    print(f"  FAQ total: {len(out)} chunk")
    return out
