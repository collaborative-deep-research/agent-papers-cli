"""Shared utilities: parallel map, checkpointing, aggregation."""

from __future__ import annotations

import json
import os
from collections import defaultdict
from multiprocessing.pool import ThreadPool
from typing import Any, Callable

from tqdm import tqdm

from .types import EvalResult, SingleEvalResult


def aggregate_results(
    single_eval_results: list[SingleEvalResult],
    default_stats: tuple[str, ...] = ("mean", "std"),
    name2stats: dict[str, tuple[str, ...]] | None = None,
) -> EvalResult:
    """Aggregate results from multiple evaluations into a single EvalResult."""
    import numpy as np

    name2stats = name2stats or {}
    name2values: dict[str, list[float]] = defaultdict(list)
    per_example_results = []

    for result in single_eval_results:
        for name, value in result.metrics.items():
            name2values[name].append(value)
        if result.score is not None:
            name2values["score"].append(result.score)
        per_example_results.append(result.__dict__)

    def _compute_stat(values: list[float], stat: str) -> float:
        if stat == "mean":
            return float(np.mean(values))
        elif stat == "std":
            return float(np.std(values))
        elif stat == "n_samples":
            return float(len(values))
        elif stat == "bootstrap_std":
            return float(
                np.std(
                    [np.mean(np.random.choice(values, len(values))) for _ in range(1000)]
                )
            )
        raise ValueError(f"Unknown {stat=}")

    final_metrics: dict[str, float] = {}
    for name, values in name2values.items():
        stats = name2stats.get(name, default_stats)
        for stat in stats:
            key = name if stat == "mean" else f"{name}:{stat}"
            final_metrics[key] = _compute_stat(values, stat)

    return EvalResult(
        score=final_metrics.pop("score", None),
        metrics=final_metrics,
        per_example_results=per_example_results,
    )


def map_with_progress(
    f: Callable,
    xs: list[Any],
    num_threads: int = 10,
    pbar: bool = True,
) -> list[Any]:
    """Apply *f* to each element of *xs* using a ThreadPool with a progress bar."""
    pbar_fn = tqdm if pbar else lambda x, *a, **kw: x

    if os.getenv("debug"):
        return list(map(f, pbar_fn(xs, total=len(xs))))

    with ThreadPool(min(num_threads, max(len(xs), 1))) as pool:
        return list(pbar_fn(pool.imap(f, xs), total=len(xs)))


def save_checkpoint(rows: list[dict], path: str) -> None:
    """Append-friendly JSONL checkpoint."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        for row in rows:
            f.write(json.dumps(row, default=str) + "\n")


def load_checkpoint(path: str) -> list[dict]:
    """Load a JSONL checkpoint file."""
    if not os.path.exists(path):
        return []
    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows
