import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

from app.agents.nodes import generate, rerank_node, retrieve, rewrite_query
from app.agents.verify import verify

GOLDEN = Path("eval/golden.jsonl")
HASIL = Path("eval/kalibrasi_verifier.json")

KARANGAN = (
    " Selain itu, seluruh ketentuan ini mulai berlaku sejak 1 Januari 1999 dan "
    "pelanggarnya dikenai denda tetap sebesar Rp5.000.000.000,00 yang disetor "
    "ke Badan Pengawas Perizinan Nasional."
)


def siapkan(question: str) -> dict[str, Any]:
    state: dict[str, Any] = {"original_query": question, "rerank_aktif": True}
    state.update(rewrite_query(state))  # type: ignore[arg-type]
    state.update({"intent": "lookup", "source_type": None, "top_k": 3})
    state.update(retrieve(state))  # type: ignore[arg-type]
    state.update(rerank_node(state))  # type: ignore[arg-type]
    state.update(generate(state))  # type: ignore[arg-type]
    return state


def main(argv: list[str]) -> None:
    soal = [json.loads(b) for b in GOLDEN.read_text(encoding="utf-8").splitlines() if b.strip()]
    soal = [s for s in soal if s["expected_source_type"] == "regulasi"]
    if "--batas" in argv:
        soal = soal[: int(argv[argv.index("--batas") + 1])]
    print(f"{len(soal)} pertanyaan x 2 sampel = {len(soal) * 2} penilaian.\n")

    sampel = []
    for i, s in enumerate(soal, 1):
        try:
            state = siapkan(s["question"])
        except Exception as e:  # noqa: BLE001
            print(f"  {s['qid']}: gagal menyiapkan, {type(e).__name__}")
            continue
        jawaban = str(state.get("answer", "")).strip()
        if jawaban.lower().startswith("tidak tahu"):
            print(f"  {s['qid']}: dilewati, jawabannya penolakan")
            continue

        for label, teks in (("supported", jawaban), ("unsupported", jawaban + KARANGAN)):
            st = dict(state)
            st["answer"] = teks
            st["verify_aktif"] = True
            hasil = verify(st)  # type: ignore[arg-type]
            sampel.append(
                {
                    "qid": s["qid"],
                    "seharusnya": label,
                    "verdict": hasil.get("verdict"),
                    "klaim_tanpa_dasar": len(hasil.get("unsupported_claims") or []),
                }
            )
            time.sleep(0.4)
        if i % 5 == 0:
            print(f"  {i}/{len(soal)}")

    if not sampel:
        raise SystemExit("Tidak ada sampel yang bisa dinilai.")

    def setuju(x: dict[str, Any]) -> bool:
        if x["seharusnya"] == "supported":
            return bool(x["verdict"] == "supported")
        return bool(x["verdict"] in ("unsupported", "partial"))

    cocok = sum(setuju(x) for x in sampel)
    print(f"\nAgreement rate: {cocok}/{len(sampel)} = {cocok / len(sampel):.1%}\n")

    for label in ("supported", "unsupported"):
        bagian = [x for x in sampel if x["seharusnya"] == label]
        if not bagian:
            continue
        benar = sum(setuju(x) for x in bagian)
        sebar = Counter(x["verdict"] for x in bagian)
        nama = "jawaban asli" if label == "supported" else "jawaban disisipi karangan"
        print(f"{nama:<28} {benar}/{len(bagian)}  verdict: {dict(sebar)}")

    lolos = [x for x in sampel if x["seharusnya"] == "unsupported" and not setuju(x)]
    if lolos:
        print(f"\nKarangan yang LOLOS tidak terdeteksi: {[x['qid'] for x in lolos]}")

    HASIL.write_text(
        json.dumps(
            {
                "catatan": (
                    "Label dibangun, bukan dilabeli tangan. Karangan yang disisipkan "
                    "kasar dan mencolok, jadi angka ini batas ATAS kemampuan verifier."
                ),
                "jumlah_sampel": len(sampel),
                "agreement_rate": round(cocok / len(sampel), 3),
                "sampel": sampel,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"\nDisimpan ke {HASIL}")


if __name__ == "__main__":
    main(sys.argv[1:])
