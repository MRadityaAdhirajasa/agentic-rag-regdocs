import math


def recall_at_k(relevan: set[str], terambil: list[set[str]], k: int) -> float:
    if not relevan:
        return 0.0
    tercakup: set[str] = set()
    for himpunan in terambil[:k]:
        tercakup |= himpunan
    return len(relevan & tercakup) / len(relevan)


def mrr(relevan: set[str], terambil: list[set[str]]) -> float:
    for i, himpunan in enumerate(terambil, start=1):
        if himpunan & relevan:
            return 1.0 / i
    return 0.0


def ndcg_at_k(relevan: set[str], terambil: list[set[str]], k: int) -> float:
    if not relevan:
        return 0.0
    dcg = sum(1 / math.log2(i + 1) for i, h in enumerate(terambil[:k], start=1) if h & relevan)
    ideal = sum(1 / math.log2(i + 1) for i in range(1, min(len(relevan), k) + 1))
    return dcg / ideal if ideal else 0.0


def ringkas(hasil: list[tuple[set[str], list[set[str]]]]) -> dict[str, float]:
    if not hasil:
        return {}
    n = len(hasil)
    return {
        "recall@5": sum(recall_at_k(r, t, 5) for r, t in hasil) / n,
        "recall@10": sum(recall_at_k(r, t, 10) for r, t in hasil) / n,
        "mrr": sum(mrr(r, t) for r, t in hasil) / n,
        "ndcg@10": sum(ndcg_at_k(r, t, 10) for r, t in hasil) / n,
        "jumlah_pertanyaan": n,
    }
