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
    output_dir: str = "evals/data/researchqa",
) -> str:
    """Download the ResearchQA test split and official subset IDs from HuggingFace.

    Returns path to the filtered JSON file (official subset only, ~100 examples).
    """
    from huggingface_hub import hf_hub_download

    filtered_path = os.path.join(output_dir, "test_official.json")
    if os.path.exists(filtered_path):
        return filtered_path

    os.makedirs(output_dir, exist_ok=True)

    # Download full test split.
    test_file = hf_hub_download(
        repo_id="realliyifei/ResearchQA",
        filename="test.json",
        repo_type="dataset",
        revision="87cdd81df0c5ea96de293859233e8e64dac3d168",
    )

    # Download official subset IDs (matches DR-Tulu's eval set).
    ids_file = hf_hub_download(
        repo_id="rl-research/researchqa_official_subset_ids",
        filename="researchqa_official_subset_ids.json",
        repo_type="dataset",
    )
    with open(ids_file) as f:
        official_ids = set(json.load(f))

    # Filter to official subset.
    with open(test_file, encoding="utf-8") as f:
        all_items = json.load(f)
    filtered = [item for item in all_items if item["id"] in official_ids]

    with open(filtered_path, "w", encoding="utf-8") as f:
        json.dump(filtered, f, ensure_ascii=False)

    logger.info("Downloaded ResearchQA: %d / %d examples (official subset)",
                len(filtered), len(all_items))
    return filtered_path


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
