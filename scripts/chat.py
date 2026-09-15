import sys

from app.agents.graph import tanya
from app.core.citation import citation


def answer(question: str) -> str:
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
