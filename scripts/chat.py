"""Chat loop CLI. Sejak Tahap 9 seluruhnya dijalankan lewat LangGraph.

Dijalankan sebagai modul (`-m`), bukan sebagai file, supaya `app/` ikut
terbaca dari root proyek:

    uv run python -m scripts.chat
    uv run python -m scripts.chat "apa itu perizinan berusaha berbasis risiko"
    uv run python -m scripts.chat "kenapa ID izin PB-UMKU hilang"

Jawaban selalu datang bersama sitasi yang bisa kamu buka sendiri: pasal dan
halaman untuk regulasi, kategori dan tanggal untuk FAQ. Itu satu-satunya cara
membuktikan sistem ini tidak mengarang.

Intent hasil routing ikut dicetak, supaya keputusan sistem bisa dinilai —
bukan cuma hasil akhirnya.
"""

import sys

from app.agents.graph import tanya
from app.core.citation import citation


def answer(question: str) -> str:
    """Sejak Tahap 9 semuanya lewat graph, termasuk routing dan penulisan ulang."""
    state = tanya(question)
    hits = state["reranked_chunks"]
    if not hits:
        return "Tidak ada dokumen yang cocok. Sudah jalankan `make ingest`?"

    baris = [f"  intent: {state['intent']}  ->  saring: {state['source_type'] or 'semua'}"]
    if state.get("alias_terpakai"):
        baris.append(f"  alias dinormalkan: {', '.join(state['alias_terpakai'])}")
    for i, h in enumerate(hits, 1):
        if not h.payload:
            continue
        baris.append(f"  [{i}] {citation(h.payload)}  (skor {h.score:.3f})")
        if h.payload.get("question"):
            baris.append(f"      {h.payload['question']}")
    sumber = "\n".join(baris)
    return f"{state['answer']}\n\nSumber:\n{sumber}"


def main(argv: list[str]) -> None:
    # --faq / --regulasi dihapus di Tahap 9: routing yang memilih sendiri,
    # dan intent yang dipilih ikut dicetak supaya keputusannya bisa dinilai
    sisa = [a for a in argv if not a.startswith("--")]

    if sisa:
        print(answer(" ".join(sisa)))
        return

    print("Ketik pertanyaan. Enter kosong atau Ctrl+C untuk keluar.\n")
    while True:
        try:
            question = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not question:
            return
        print(f"\n{answer(question)}\n")


if __name__ == "__main__":
    main(sys.argv[1:])
