"""Deep Research Bench (DRB): format converter for RACE/FACT scoring.

Generates research reports using Claude Code, then converts to DRB format
(article + citations + deduped URLs) for external evaluation.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Callable

from ..common import map_with_progress
from ..types import SingleEvalResult
from .base import Eval

logger = logging.getLogger(__name__)

DEFAULT_SKILL = "deep-research"


# ---------------------------------------------------------------------------
# DRB format conversion
# ---------------------------------------------------------------------------


def _parse_and_format_citations(text: str) -> tuple[str, list[str], dict[str, list[str]]]:
    """Parse <cite> tags, reformat to [id], extract id -> text mapping."""
    citation_ids: list[str] = []
    id_to_text: dict[str, list[str]] = {}

    def replacer(match: re.Match) -> str:
        ids = match.group(1).split(",")
        content = match.group(2)
        for cid in ids:
            if cid not in citation_ids:
                citation_ids.append(cid)
            id_to_text.setdefault(cid, []).append(content)
        formatted = " ".join(f"[{cid}]" for cid in ids)
        return f". {content} {formatted}."

    pattern = re.compile(r'<cite id="([^"]+)">([^<]+)</cite>')
    formatted_text = pattern.sub(replacer, text)
    return formatted_text, citation_ids, id_to_text


def _format_example(gen: dict[str, Any]) -> dict[str, Any]:
    """Convert a single generation to DRB format."""
    item = gen["item"]
    output: dict[str, Any] = {
        "id": item.get("id") or item.get("example_id", ""),
        "prompt": item.get("problem") or item.get("query", ""),
        "article": "",
        "citations_deduped": {},
        "citations": [],
    }

    response_text = gen.get("response_text", "")
    article, citation_ids, id_to_text = _parse_and_format_citations(response_text)

    # Renumber citations
    references = []
    for i, cid in enumerate(citation_ids):
        article = article.replace(cid, str(i + 1))
        references.append(f"[{i + 1}]")

    if re.search(r"[\u4e00-\u9fff]", article):
        output["article"] = article + "\n\n 参考文献: " + "\n".join(references)
    else:
        output["article"] = article + "\n\n References: " + "\n".join(references)

    return output


# ---------------------------------------------------------------------------
# Eval
# ---------------------------------------------------------------------------


class DRBEval(Eval):
    """DRB — generates research reports and exports DRB-format JSONL."""

    def __init__(
        self,
        data_path: str,
        num_examples: int | None = None,
        n_threads: int = 10,
        output_dir: str = "evals/results",
        skill: str | None = DEFAULT_SKILL,
    ):
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
            query = item.get("problem") or item.get("query", "")
            prompt = self._make_prompt(query)
            result = run(prompt)
            return {
                "item": item,
                "response_text": result.get("result", ""),
                "claude": result,
            }

        return map_with_progress(
            generate_single, self.items, num_threads=self.n_threads
        )

    def evaluate(self, generation_data: list[dict[str, Any]]) -> list[SingleEvalResult]:
        """Convert to DRB format and save.  External RACE/FACT scoring."""
        drb_rows = []
        results = []
        for i, gen in enumerate(generation_data):
            try:
                formatted = _format_example(gen)
            except Exception:
                logger.error("Failed to format DRB example %d", i)
                formatted = {"id": str(i), "article": "", "citations": []}
            drb_rows.append(formatted)
            results.append(SingleEvalResult(
                id=str(i), score=None, metrics={},
                metadata={"n_citations": len(formatted.get("citations", []))},
            ))

        os.makedirs(self.output_dir, exist_ok=True)
        out_path = os.path.join(self.output_dir, "drb_format.jsonl")
        with open(out_path, "w") as f:
            for row in drb_rows:
                f.write(json.dumps(row) + "\n")
        logger.info("Wrote DRB-format output to %s", out_path)
        return results
