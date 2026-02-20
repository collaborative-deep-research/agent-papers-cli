"""Core data types for the evaluation harness."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

Message = dict[str, Any]
MessageList = list[Message]


@dataclass
class SamplerResponse:
    """Response from a sampler (Claude API with tool use)."""

    response_text: str
    messages: MessageList
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SingleEvalResult:
    """Result of evaluating a single example."""

    id: str
    score: float | None
    metrics: dict[str, float] = field(default_factory=dict)
    convo: MessageList | None = None
    metadata: dict[str, Any] | None = None


@dataclass
class EvalResult:
    """Aggregated result of running an evaluation."""

    score: float | None
    metrics: dict[str, float] | None = None
    per_example_results: list[dict[str, Any]] | None = None
