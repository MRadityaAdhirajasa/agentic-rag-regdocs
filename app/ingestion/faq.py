"""FAQ OSS BKPM (6 file JSON) -> chunk. Satu item = satu chunk, tanpa dipotong.

Keputusan yang menentukan kualitas retrieval di sini: **yang di-embed adalah
question + answer, bukan salah satu.** Question mencocokkan cara orang
bertanya, answer membawa kata kunci substansinya. Question ditaruh di depan
karena model embedding memberi bobot lebih pada awal teks — ini pengganti
parameter `title` milik Gemini, yang tidak ada di endpoint OpenRouter.

Field `notes`, `input_method`, dan `base_url` sengaja dibuang: tidak dipakai
untuk retrieval maupun sitasi.
"""

import json
from pathlib import Path
from typing import Any

FAQ_DIR = Path("dokumen/faq")


def records(directory: Path = FAQ_DIR) -> list[dict[str, Any]]:
    files = sorted(directory.glob("*.json"))
    if not files:
        raise SystemExit(f"Tidak ada file JSON di {directory}.")

    out: list[dict[str, Any]] = []
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        sumber = data["source"]
        kategori = sumber["category"]
        items = data["items"]
        for item in items:
            teks = f"{item['question']}\n\n{item['answer']}"
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
                        # tanggal dari file FAQ itu sendiri, bukan tanggal hari ini
                        "tanggal_akses": sumber.get("last_updated", ""),
                    },
                }
            )
        print(f"  {path.name}: {len(items)} item — {kategori}")
    print(f"  FAQ total: {len(out)} chunk")
    return out
