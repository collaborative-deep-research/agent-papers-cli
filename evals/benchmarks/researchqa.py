"""ResearchQA benchmark: coverage-based evaluation of research question answers.

Dataset: https://huggingface.co/datasets/realliyifei/ResearchQA
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from dataclasses import dataclass
from typing import Any, Callable

from ..common import map_with_progress
from ..graders import grade_coverage
from ..types import SingleEvalResult
from .base import Eval

logger = logging.getLogger(__name__)

DEFAULT_SKILL = "deep-research"


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


@dataclass
class RubricItem:
    rubric_item: str
    type: str


@dataclass
class ResearchQAItem:
    id: str
    general_domain: str
    subdomain: str
    field: str
    query: str
    date: str
    rubric: list[RubricItem]


def download_researchqa_dataset(
    split: str = "test.json",
    output_dir: str = "evals/data/researchqa",
) -> str:
    """Download the ResearchQA dataset from HuggingFace."""
    from huggingface_hub import hf_hub_download

    output_path = os.path.join(output_dir, split)
    if not os.path.exists(output_path):
        os.makedirs(output_dir, exist_ok=True)
        file_path = hf_hub_download(
            repo_id="realliyifei/ResearchQA",
            filename=split,
            repo_type="dataset",
            revision="87cdd81df0c5ea96de293859233e8e64dac3d168",
        )
        shutil.copy(file_path, output_path)
    return output_path


def load_researchqa_data(json_path: str) -> list[ResearchQAItem]:
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    items = []
    for item in data:
        rubric = [RubricItem(**r) for r in item["rubric"]]
        items.append(
            ResearchQAItem(
                id=item["id"],
                general_domain=item["general_domain"],
                subdomain=item["subdomain"],
                field=item["field"],
                query=item["query"],
                date=item["date"],
                rubric=rubric,
            )
        )
    return items


# ---------------------------------------------------------------------------
# Eval
# ---------------------------------------------------------------------------


class ResearchQAEval(Eval):
    def __init__(
        self,
        data_path: str | None = None,
        num_examples: int | None = None,
        n_threads: int = 10,
        grader_model: str = "gpt-4.1-mini",
        skill: str | None = DEFAULT_SKILL,
    ):
        if data_path is None:
            data_path = download_researchqa_dataset()
        self.items = load_researchqa_data(data_path)
        if num_examples and num_examples < len(self.items):
            self.items = self.items[:num_examples]
        self.data_path = data_path
        self.n_threads = n_threads
        self.grader_model = grader_model
        self.skill = skill

    def _make_prompt(self, query: str) -> str:
        if self.skill:
            return f"/{self.skill} {query}"
        return query

    def generate(self, run: Callable[..., dict]) -> list[dict[str, Any]]:
        def generate_single(item: ResearchQAItem) -> dict[str, Any]:
            prompt = self._make_prompt(item.query)
            result = run(prompt)
            return {
                "item_id": item.id,
                "query": item.query,
                "field": item.field,
                "response_text": result.get("result", ""),
                "claude": result,
                "rubric": [
                    {"rubric_item": r.rubric_item, "type": r.type}
                    for r in item.rubric
                ],
            }

        return map_with_progress(
            generate_single, self.items, num_threads=self.n_threads
        )

    def evaluate(self, generation_data: list[dict[str, Any]]) -> list[SingleEvalResult]:
        def evaluate_single(gen: dict[str, Any]) -> SingleEvalResult:
            rubric_items = [r["rubric_item"] for r in gen["rubric"]]
            coverage_score, rubric_judges = grade_coverage(
                gen["response_text"],
                rubric_items,
                model=self.grader_model,
            )
            return SingleEvalResult(
                id=gen["item_id"],
                score=coverage_score,
                metrics={"coverage_score": coverage_score},
                metadata={
                    "field": gen["field"],
                    "rubric_judges": rubric_judges,
                    "num_turns": gen["claude"].get("num_turns"),
                    "cost_usd": gen["claude"].get("total_cost_usd"),
                },
            )

        return map_with_progress(
            evaluate_single, generation_data, num_threads=self.n_threads
        )
