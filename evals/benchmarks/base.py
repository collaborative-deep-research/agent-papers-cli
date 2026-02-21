"""Base evaluation class.

All benchmarks follow the generate -> evaluate -> aggregate pattern.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable

from ..common import aggregate_results
from ..types import EvalResult, SingleEvalResult


class Eval(ABC):
    """Abstract base class for an evaluation benchmark."""

    @abstractmethod
    def generate(self, run: Callable[..., dict]) -> list[dict[str, Any]]:
        """Generate responses for every example.

        *run* is ``evals.claude.run_claude`` (or any function with the
        same ``(prompt, **kwargs) -> dict`` signature).
        """
        ...

    @abstractmethod
    def evaluate(self, generation_data: list[dict[str, Any]]) -> list[SingleEvalResult]:
        """Score a list of generated outputs."""
        ...

    def __call__(self, run: Callable[..., dict]) -> tuple[list[dict[str, Any]], EvalResult]:
        """Run end-to-end: generate, evaluate, aggregate.

        Returns ``(gen_data, eval_result)`` so callers can persist the
        full generation data (including trajectories) alongside scores.
        """
        gen_data = self.generate(run)
        results = self.evaluate(gen_data)
        return gen_data, aggregate_results(results)
