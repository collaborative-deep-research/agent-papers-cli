"""Base evaluation class.

All benchmarks follow the generate -> evaluate -> aggregate pattern.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..common import aggregate_results
from ..sampler import AnthropicToolSampler
from ..types import EvalResult, SingleEvalResult


class Eval(ABC):
    """Abstract base class for an evaluation benchmark."""

    @abstractmethod
    def generate(self, sampler: AnthropicToolSampler) -> list[dict[str, Any]]:
        """Generate responses for every example. Returns raw generation data."""
        ...

    @abstractmethod
    def evaluate(self, generation_data: list[dict[str, Any]]) -> list[SingleEvalResult]:
        """Score a list of generated outputs."""
        ...

    def __call__(self, sampler: AnthropicToolSampler) -> EvalResult:
        """Run end-to-end: generate, evaluate, aggregate."""
        gen_data = self.generate(sampler)
        results = self.evaluate(gen_data)
        return aggregate_results(results)
