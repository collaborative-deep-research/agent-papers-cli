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
from typing import Any, Callable, Literal

import numpy as np

from ..common import map_with_progress
from ..graders import grade_rubric
from ..types import EvalResult, SingleEvalResult
from .base import Eval

logger = logging.getLogger(__name__)

DEFAULT_SKILL = "deep-research"

INPUT_URLS = {
    "all": "https://openaipublic.blob.core.windows.net/simple-evals/healthbench/2025-05-07-06-14-12_oss_eval.jsonl",
    "hard": "https://openaipublic.blob.core.windows.net/simple-evals/healthbench/hard_2025-05-08-21-00-10.jsonl",
    "consensus": "https://openaipublic.blob.core.windows.net/simple-evals/healthbench/consensus_2025-05-09-20-00-46.jsonl",
}


def _load_healthbench_data(
    subset: str = "all",
    cache_dir: str = "evals/data/healthbench",
) -> list[dict[str, Any]]:
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
        skill: str | None = DEFAULT_SKILL,
    ):
        examples = _load_healthbench_data(subset)
        if num_examples is not None and num_examples < len(examples):
            rng = random.Random(0)
            examples = rng.sample(examples, num_examples)
        self.examples = examples
        self.n_threads = n_threads
        self.grader_model = grader_model
        self.skill = skill

    def _make_prompt(self, messages: list[dict[str, str]]) -> str:
        """Format multi-turn HealthBench prompt for ``claude -p``."""
        if len(messages) == 1:
            body = messages[0]["content"]
        else:
            parts = []
            for msg in messages[:-1]:
                parts.append(f"{msg['role'].capitalize()}: {msg['content']}")
            history = "\n\n".join(parts)
            body = (
                f"<conversation_history>\n{history}\n</conversation_history>\n\n"
                f"{messages[-1]['content']}"
            )
        if self.skill:
            return f"/{self.skill} {body}"
        return body

    def generate(self, run: Callable[..., dict]) -> list[dict[str, Any]]:
        def generate_single(example: dict[str, Any]) -> dict[str, Any]:
            prompt = self._make_prompt(example["prompt"])
            result = run(prompt)
            return {
                "row": example,
                "response_text": result.get("result", ""),
                "claude": result,
            }

        return map_with_progress(
            generate_single, self.examples, num_threads=self.n_threads
        )

    def evaluate(self, generation_data: list[dict[str, Any]]) -> list[SingleEvalResult]:
        def evaluate_single(gen: dict[str, Any]) -> SingleEvalResult:
            row = gen["row"]
            rubric_items = row["rubrics"]
            if rubric_items and not isinstance(rubric_items[0], dict):
                rubric_items = [r.to_dict() for r in rubric_items]

            score, grading_results = grade_rubric(
                row["prompt"],
                gen["response_text"],
                rubric_items,
                model=self.grader_model,
            )

            metrics: dict[str, float] = {"overall_score": score}
            for tag in row.get("example_tags", []):
                metrics[tag] = score
            tag_items: dict[str, list[tuple[dict, dict]]] = defaultdict(list)
            for item, grade in zip(rubric_items, grading_results):
                for tag in item.get("tags", []):
                    tag_items[tag].append((item, grade))
            for tag, pairs in tag_items.items():
                total = sum(it["points"] for it, _ in pairs if it["points"] > 0)
                if total > 0:
                    achieved = sum(it["points"] for it, gr in pairs if gr.get("criteria_met"))
                    metrics[tag] = achieved / total

            return SingleEvalResult(
                id=row["id"],
                score=score,
                metrics=metrics,
                metadata={"grading_results": grading_results},
            )

        return map_with_progress(
            evaluate_single, generation_data, num_threads=self.n_threads
        )

    def __call__(self, run: Callable[..., dict]) -> EvalResult:
        """Override to use clipped-mean aggregation."""
        gen_data = self.generate(run)
        results = self.evaluate(gen_data)

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
