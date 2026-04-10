"""Data types for evaluation results."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SingleEvalResult:
    """Result of evaluating a single example."""

    id: str
    score: float | None
    metrics: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] | None = None


@dataclass
class EvalResult:
    """Aggregated result of running an evaluation."""

    score: float | None
    metrics: dict[str, float] | None = None
    per_example_results: list[dict[str, Any]] | None = None
