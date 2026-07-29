"""Compare retrieval approaches on the ground-truth dataset: Hit Rate and MRR."""
import csv
from pathlib import Path

from app.search import hybrid_search, text_search, vector_search

K = 5


def evaluate(search_fn, ground_truth: list[dict]) -> tuple[float, float]:
    hits, rr = 0, 0.0
    for row in ground_truth:
        results = search_fn(row["question"], k=K)[:K]
        ranks = [h.chunk_id for h in results]
        if int(row["chunk_id"]) in ranks:
            hits += 1
            rr += 1 / (ranks.index(int(row["chunk_id"])) + 1)
    n = len(ground_truth)
    return hits / n, rr / n     # hit rate, MRR


def main() -> None:
    with Path("evaluation/ground_truth.csv").open() as f:
        gt = list(csv.DictReader(f))
    print(f"{len(gt)} questions, k={K}\n")
    print(f"{'approach':<12} {'hit rate':>8} {'MRR':>8}")
    for name, fn in [("text", text_search), ("vector", vector_search),
                     ("hybrid", hybrid_search)]:
        hit_rate, mrr = evaluate(fn, gt)
        print(f"{name:<12} {hit_rate:>8.3f} {mrr:>8.3f}")


if __name__ == "__main__":
    main()