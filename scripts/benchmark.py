import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any

from app.agents.graph import tanya

GOLDEN = Path("eval/golden.jsonl")
HASIL = Path("eval/benchmark.json")


def persentil(nilai: list[float], p: float) -> float:
    if not nilai:
        return 0.0
    urut = sorted(nilai)
    i = min(int(round(p / 100 * (len(urut) - 1))), len(urut) - 1)
    return urut[i]


def jalankan(soal: list[dict[str, Any]], verify: bool) -> dict[str, Any]:
    label = "verify ON " if verify else "verify OFF"
    lama: list[float] = []
    token_total, token_in, token_out, biaya, panggilan = 0, 0, 0, 0.0, 0
    verdict: dict[str, int] = {}
    retry = 0
    negatif_benar = 0
    negatif_jumlah = 0

    for i, s in enumerate(soal, 1):
        mulai = time.perf_counter()
        try:
            st = tanya(s["question"], verify=verify)
        except Exception as e:  # noqa: BLE001
            print(f"  {label} {s['qid']}: GAGAL {type(e).__name__}: {str(e)[:80]}")
            continue
        lama.append((time.perf_counter() - mulai) * 1000)

        t = st.get("token") or {}
        token_total += int(t.get("token_total", 0))
        token_in += int(t.get("token_input", 0))
        token_out += int(t.get("token_output", 0))
        biaya += float(t.get("biaya_usd", 0.0))
        panggilan += int(t.get("panggilan_llm", 0))
        retry += int(st.get("retry_count", 0))

        v = str(st.get("verdict", "tidak_diverifikasi"))
        verdict[v] = verdict.get(v, 0) + 1

        if s["category"] == "negatif":
            negatif_jumlah += 1
            menolak = str(st.get("answer", "")).strip().lower().startswith("tidak tahu")
            if menolak or v == "unsupported":
                negatif_benar += 1

        if i % 5 == 0:
            print(f"  {label} {i}/{len(soal)}")

    n = len(lama) or 1
    didukung = verdict.get("supported", 0)
    dinilai = sum(v for k, v in verdict.items() if k in ("supported", "partial", "unsupported"))
    return {
        "jumlah_pertanyaan": len(lama),
        "p50_ms": round(statistics.median(lama), 0) if lama else 0,
        "p95_ms": round(persentil(lama, 95), 0),
        "rata_ms": round(sum(lama) / n, 0),
        "panggilan_llm_per_pertanyaan": round(panggilan / n, 2),
        "token_input": token_in,
        "token_output": token_out,
        "token_per_pertanyaan": round(token_total / n, 0),
        "biaya_usd_total": round(biaya, 5),
        "biaya_usd_per_1000_pertanyaan": round(biaya / n * 1000, 3),
        "retry_total": retry,
        "verdict": verdict,
        "faithfulness": round(didukung / dinilai, 3) if dinilai else None,
        "negatif_benar": f"{negatif_benar}/{negatif_jumlah}" if negatif_jumlah else "-",
    }


def baris(nama: str, mati: Any, nyala: Any) -> str:
    return f"| {nama:<32} | {mati!s:>14} | {nyala!s:>14} |"


def main(argv: list[str]) -> None:
    soal = [json.loads(b) for b in GOLDEN.read_text(encoding="utf-8").splitlines() if b.strip()]
    if "--batas" in argv:
        soal = soal[: int(argv[argv.index("--batas") + 1])]
    print(f"{len(soal)} pertanyaan, dijalankan dua kali (verify off lalu on).\n")

    mati = jalankan(soal, verify=False)
    nyala = jalankan(soal, verify=True)

    print("\n| " + "metrik".ljust(32) + " |     verify OFF |      verify ON |")
    print("|" + "-" * 34 + "|" + "-" * 16 + "|" + "-" * 16 + "|")
    for kunci, label in [
        ("p50_ms", "latensi p50 (ms)"),
        ("p95_ms", "latensi p95 (ms)"),
        ("rata_ms", "latensi rata-rata (ms)"),
        ("panggilan_llm_per_pertanyaan", "panggilan LLM / pertanyaan"),
        ("token_per_pertanyaan", "token / pertanyaan"),
        ("biaya_usd_per_1000_pertanyaan", "biaya USD / 1000 pertanyaan"),
        ("retry_total", "total percobaan ulang"),
        ("faithfulness", "faithfulness (verdict supported)"),
        ("negatif_benar", "negatif dijawab tidak tahu"),
    ]:
        print(baris(label, mati.get(kunci), nyala.get(kunci)))

    HASIL.write_text(
        json.dumps(
            {
                "catatan": (
                    "Diukur lokal, korpus 829 chunk, tier gratis. Biaya dihitung "
                    "dengan harga tier berbayar gemini-3.1-flash-lite "
                    "(USD 0,25/1J token input, USD 1,50/1J output)."
                ),
                "verify_off": mati,
                "verify_on": nyala,
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
