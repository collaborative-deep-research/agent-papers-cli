"""SQAv2 benchmark: format converter for ASTA evaluation.

Generates responses using Claude Code, then converts output to ASTA format
(sections + citations) for external evaluation via ``inspect eval astabench/sqa``.

Dataset: https://huggingface.co/datasets/allenai/asta-bench
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
from typing import Any, Callable

from ..common import map_with_progress
from ..types import SingleEvalResult
from .base import Eval

logger = logging.getLogger(__name__)

DEFAULT_SKILL = "deep-research"


def download_sqa_dataset(
    output_dir: str = "evals/data/sqa",
) -> str:
    """Download SQAv2 rubrics from HuggingFace ``allenai/asta-bench``."""
    from huggingface_hub import hf_hub_download

    output_path = os.path.join(output_dir, "rubrics_v2_recomputed.json")
    if not os.path.exists(output_path):
        os.makedirs(output_dir, exist_ok=True)
        file_path = hf_hub_download(
            repo_id="allenai/asta-bench",
            filename="tasks/sqa/rubrics_v2_recomputed.json",
            repo_type="dataset",
        )
        shutil.copy(file_path, output_path)
        logger.info("Downloaded SQA dataset to %s", output_path)
    return output_path


# ---------------------------------------------------------------------------
# ASTA format conversion
# ---------------------------------------------------------------------------


def _change_citations_asta_format(text: str) -> tuple[str, list[str]]:
    """Convert <cite id="xxx">text</cite> to [id] format."""
    citation_ids: list[str] = []
    pattern = r'[ \t]*<cite id=["\']?([^"\'>\s]+)["\']?>\s*(.*?)\s*</cite>[ \t]*'

    def repl(match: re.Match) -> str:
        ids = match.group(1).split(",")
        snippet = match.group(2).strip()
        citation_ids.extend(ids)
        cites = "".join(f"[{cid}]" for cid in ids)
        if snippet and snippet[-1] in ".!?,":
            return " " + snippet[:-1] + " " + cites + snippet[-1] + " "
        return " " + snippet + " " + cites + " "

    new_text = re.sub(pattern, repl, text)
    new_text = new_text.replace("  ", " ").strip().replace(" .", ".")
    return new_text, citation_ids


def _parse_answer_to_sections(response_text: str) -> list[dict[str, Any]]:
    """Parse a response into ASTA sections with citations."""
    raw_parts = response_text.strip().split("\n\n")
    merged: list[str] = []
    current: str | None = None
    for part in raw_parts:
        if part.startswith("#"):
            if current is not None:
                merged.append(current)
            current = part
        else:
            if current is not None:
                current += "\n\n" + part
            else:
                merged.append(part)
    if current is not None:
        merged.append(current)

    merged = [
        s for s in merged
        if not (s.strip().startswith("#") and len(s.strip().split("\n")) == 1)
    ]

    sections = []
    for section_text in merged:
        title_match = re.match(r"#+\s*([^\n]*)", section_text)
        if title_match:
            title = "# " + title_match.group(1).strip()
            body = section_text[title_match.end():].strip()
        else:
            title = None
            body = section_text.strip()

        clean_text, citation_ids = _change_citations_asta_format(body)
        section_citations = [{"id": f"[{cid}]"} for cid in set(citation_ids)]

        sections.append({
            "title": title,
            "text": clean_text,
            "citations": section_citations,
        })

    return sections


# ---------------------------------------------------------------------------
# Eval
# ---------------------------------------------------------------------------


class SQAEval(Eval):
    """SQAv2 — generates responses and exports ASTA-format JSONL."""

    def __init__(
        self,
        data_path: str | None = None,
        num_examples: int | None = None,
        n_threads: int = 10,
        output_dir: str = "evals/results",
        skill: str | None = DEFAULT_SKILL,
    ):
        if data_path is None:
            data_path = download_sqa_dataset()
        with open(data_path) as f:
            if data_path.endswith(".jsonl"):
                self.items = [json.loads(line) for line in f if line.strip()]
            else:
                self.items = json.load(f)
        if num_examples and num_examples < len(self.items):
            self.items = self.items[:num_examples]
        self.n_threads = n_threads
        self.output_dir = output_dir
        self.skill = skill

    def _make_prompt(self, query: str) -> str:
        if self.skill:
            return f"/{self.skill} {query}"
        return query

    def generate(self, run: Callable[..., dict]) -> list[dict[str, Any]]:
        def generate_single(item: dict[str, Any]) -> dict[str, Any]:
            question = item.get("question") or item.get("problem") or item.get("query", "")
            prompt = self._make_prompt(question)
            result = run(prompt)
            return {
                "item": item,
                "question": question,
                "response_text": result.get("result", ""),
                "claude": result,
            }

        return map_with_progress(
            generate_single, self.items, num_threads=self.n_threads
        )

    def evaluate(self, generation_data: list[dict[str, Any]]) -> list[SingleEvalResult]:
        """Convert to ASTA format and save.  External scoring via ``inspect eval``."""
        asta_rows = []
        results = []
        for i, gen in enumerate(generation_data):
            sections = _parse_answer_to_sections(gen["response_text"])
            asta_rows.append({
                "question": gen["question"],
                "response": {"sections": sections},
            })
            results.append(SingleEvalResult(
                id=str(i), score=None, metrics={},
                metadata={"asta_sections": len(sections)},
            ))

        os.makedirs(self.output_dir, exist_ok=True)
        out_path = os.path.join(self.output_dir, "sqa_asta_format.jsonl")
        with open(out_path, "w") as f:
            json.dump(asta_rows, f, indent=2)
        logger.info("Wrote ASTA-format output to %s", out_path)
        return results
