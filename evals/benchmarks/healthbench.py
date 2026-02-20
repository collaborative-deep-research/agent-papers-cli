"""HealthBench benchmark: rubric-based evaluation of health/medical answers.

Data loaded from OpenAI public blob storage.
"""

from __future__ import annotations

import json
import logging
import os
import random
import urllib.request
from collections import defaultdict
from typing import Any, Literal

import numpy as np

from ..common import map_with_progress
from ..graders import grade_rubric
from ..sampler import ClaudeCodeSampler
from ..types import EvalResult, SingleEvalResult
from .base import Eval

logger = logging.getLogger(__name__)

INPUT_URLS = {
    "all": "https://openaipublic.blob.core.windows.net/simple-evals/healthbench/2025-05-07-06-14-12_oss_eval.jsonl",
    "hard": "https://openaipublic.blob.core.windows.net/simple-evals/healthbench/hard_2025-05-08-21-00-10.jsonl",
    "consensus": "https://openaipublic.blob.core.windows.net/simple-evals/healthbench/consensus_2025-05-09-20-00-46.jsonl",
}


def _load_healthbench_data(
    subset: str = "all",
    cache_dir: str = "evals/data/healthbench",
) -> list[dict[str, Any]]:
    """Load HealthBench examples (downloads and caches locally)."""
    url = INPUT_URLS[subset]
    filename = url.rsplit("/", 1)[-1]
    local_path = os.path.join(cache_dir, filename)

    if os.path.exists(local_path):
        with open(local_path) as f:
            examples = [json.loads(line) for line in f]
    else:
        os.makedirs(cache_dir, exist_ok=True)
        with urllib.request.urlopen(url) as resp:
            examples = [json.loads(line.decode("utf-8")) for line in resp]
        with open(local_path, "w") as f:
            for ex in examples:
                f.write(json.dumps(ex) + "\n")

    return examples


def _clipped_mean(values: list[float]) -> float:
    return float(np.clip(np.mean(values), 0, 1))


class HealthBenchEval(Eval):
    def __init__(
        self,
        subset: Literal["all", "hard", "consensus"] = "all",
        num_examples: int | None = None,
        n_threads: int = 10,
        grader_model: str = "gpt-4.1-mini",
    ):
        examples = _load_healthbench_data(subset)
        if num_examples is not None and num_examples < len(examples):
            rng = random.Random(0)
            examples = rng.sample(examples, num_examples)
        self.examples = examples
        self.n_threads = n_threads
        self.grader_model = grader_model

    def generate(self, sampler: ClaudeCodeSampler) -> list[dict[str, Any]]:
        """Generate responses for each HealthBench prompt."""

        def generate_single(example: dict[str, Any]) -> dict[str, Any]:
            prompt_messages = example["prompt"]
            response = sampler(prompt_messages)
            return {
                "row": example,
                "response_text": response.response_text,
                "messages": response.messages,
                "tool_calls": response.tool_calls,
                "metadata": response.metadata,
            }

        return map_with_progress(
            generate_single, self.examples, num_threads=self.n_threads
        )

    def evaluate(self, generation_data: list[dict[str, Any]]) -> list[SingleEvalResult]:
        """Evaluate responses against rubric items."""

        def evaluate_single(gen: dict[str, Any]) -> SingleEvalResult:
            row = gen["row"]
            rubric_dicts = row["rubrics"]
            # Ensure rubric items are dicts
            if rubric_dicts and isinstance(rubric_dicts[0], dict):
                rubric_items = rubric_dicts
            else:
                rubric_items = [r.to_dict() if hasattr(r, "to_dict") else r for r in rubric_dicts]

            prompt_messages = gen.get("messages", row["prompt"])
            # Use only the original prompt for grading (not tool-use conversation)
            original_prompt = row["prompt"]

            score, grading_results = grade_rubric(
                original_prompt,
                gen["response_text"],
                rubric_items,
                model=self.grader_model,
            )

            # Compute per-tag scores
            metrics: dict[str, float] = {"overall_score": score}
            # Example-level tags
            for tag in row.get("example_tags", []):
                metrics[tag] = score
            # Rubric-level tags
            tag_items: dict[str, list[tuple[dict, dict]]] = defaultdict(list)
            for item, grade in zip(rubric_items, grading_results):
                for tag in item.get("tags", []):
                    tag_items[tag].append((item, grade))
            for tag, pairs in tag_items.items():
                total = sum(it["points"] for it, _ in pairs if it["points"] > 0)
                if total > 0:
                    achieved = sum(
                        it["points"] for it, gr in pairs if gr.get("criteria_met")
                    )
                    metrics[tag] = achieved / total

            return SingleEvalResult(
                id=row["id"],
                score=score,
                metrics=metrics,
                convo=gen.get("messages"),
                metadata={"grading_results": grading_results},
            )

        return map_with_progress(
            evaluate_single, generation_data, num_threads=self.n_threads
        )

    def __call__(self, sampler: ClaudeCodeSampler) -> EvalResult:
        """Override to use clipped mean aggregation."""
        gen_data = self.generate(sampler)
        results = self.evaluate(gen_data)

        # Clipped-mean aggregation (HealthBench-specific)
        name2values: dict[str, list[float]] = defaultdict(list)
        per_example_results = []

        for r in results:
            for name, value in r.metrics.items():
                name2values[name].append(value)
            if r.score is not None:
                name2values["score"].append(r.score)
            per_example_results.append(r.__dict__)

        final_metrics: dict[str, float] = {}
        for name, values in name2values.items():
            final_metrics[name] = _clipped_mean(values)
            final_metrics[f"{name}:n_samples"] = float(len(values))
            bootstrap = [np.random.choice(values, len(values)) for _ in range(1000)]
            final_metrics[f"{name}:bootstrap_std"] = float(
                np.std([_clipped_mean(list(s)) for s in bootstrap])
            )

        return EvalResult(
            score=final_metrics.pop("score", None),
            metrics=final_metrics,
            per_example_results=per_example_results,
        )
