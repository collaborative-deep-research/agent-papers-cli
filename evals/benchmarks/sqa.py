"""SQAv2 benchmark: format converter for ASTA evaluation.

Generates responses using our tools, then converts output to ASTA format
(sections + citations) for external evaluation via ``inspect eval astabench/sqa``.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from ..common import map_with_progress, save_checkpoint
from ..sampler import ClaudeCodeSampler
from ..types import SingleEvalResult
from .base import Eval

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ASTA format conversion (adapted from DR-Tulu convert_to_asta_format.py)
# ---------------------------------------------------------------------------


def _extract_citations_from_tool_calls(tool_calls: list[dict[str, Any]]) -> dict[str, str]:
    """Extract snippet-id -> content mapping from tool call outputs."""
    citations: dict[str, str] = {}
    for call in tool_calls:
        output = call.get("output", "")
        # Match <snippet id="xxx">...</snippet> patterns
        for pattern in [
            r'<snippets?\s+id=["\']?([^"\'>\s]+)["\']?[^>]*>(.*?)</snippets?>',
            r'<webpage?\s+id=["\']?([^"\'>\s]+)["\']?[^>]*>(.*?)</webpage?>',
        ]:
            for m in re.finditer(pattern, output, re.DOTALL):
                citations[m.group(1).strip()] = m.group(2).strip()
    return citations


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


def _extract_title_snippet(text: str) -> tuple[str | None, str]:
    """Parse Title: ... / Snippet: ... from citation content."""
    m = re.match(r"^Title:\s*(.*?)\nSnippet:\s*(.*)$", text, re.DOTALL)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return None, text


def _parse_answer_to_sections(
    response_text: str,
    tool_calls: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Parse a response into ASTA sections with citations."""
    # Merge headings with their body text
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

    # Remove heading-only sections
    merged = [
        s for s in merged
        if not (s.strip().startswith("#") and len(s.strip().split("\n")) == 1)
    ]

    snippets = _extract_citations_from_tool_calls(tool_calls)

    sections = []
    for section_text in merged:
        title_match = re.match(r"#+\s*([^\n]*)", section_text)
        if title_match:
            title = "# " + title_match.group(1).strip()
            body = section_text[title_match.end() :].strip()
        else:
            title = None
            body = section_text.strip()

        clean_text, citation_ids = _change_citations_asta_format(body)

        section_citations = []
        for cid in set(citation_ids):
            if cid in snippets:
                cit_title, cit_snippet = _extract_title_snippet(snippets[cid])
                section_citations.append({
                    "id": f"[{cid}]",
                    "title": cit_title,
                    "snippets": [cit_snippet],
                })

        sections.append({
            "title": title,
            "text": clean_text,
            "citations": section_citations,
        })

    return sections


# ---------------------------------------------------------------------------
# Eval class
# ---------------------------------------------------------------------------


class SQAEval(Eval):
    """SQAv2 evaluation — generates responses and exports ASTA-format JSONL."""

    def __init__(
        self,
        data_path: str,
        num_examples: int | None = None,
        n_threads: int = 10,
        output_dir: str = "evals/results",
    ):
        with open(data_path) as f:
            if data_path.endswith(".jsonl"):
                self.items = [json.loads(line) for line in f if line.strip()]
            else:
                self.items = json.load(f)
        if num_examples and num_examples < len(self.items):
            self.items = self.items[:num_examples]
        self.data_path = data_path
        self.n_threads = n_threads
        self.output_dir = output_dir

    def generate(self, sampler: ClaudeCodeSampler) -> list[dict[str, Any]]:
        """Generate responses for each SQA question."""

        def generate_single(item: dict[str, Any]) -> dict[str, Any]:
            question = item.get("question") or item.get("problem") or item.get("query", "")
            prompt = [{"role": "user", "content": question}]
            response = sampler(prompt)
            return {
                "item": item,
                "question": question,
                "response_text": response.response_text,
                "messages": response.messages,
                "tool_calls": response.tool_calls,
                "metadata": response.metadata,
            }

        return map_with_progress(
            generate_single, self.items, num_threads=self.n_threads
        )

    def evaluate(self, generation_data: list[dict[str, Any]]) -> list[SingleEvalResult]:
        """Convert to ASTA format and save. Returns placeholder results.

        Actual scoring is deferred to the external ASTA evaluator:
            inspect eval astabench/sqa
        """
        asta_rows = []
        results = []

        for i, gen in enumerate(generation_data):
            sections = _parse_answer_to_sections(
                gen["response_text"],
                gen.get("tool_calls", []),
            )
            asta_rows.append({
                "question": gen["question"],
                "response": {"sections": sections},
            })
            results.append(
                SingleEvalResult(
                    id=str(i),
                    score=None,
                    metrics={},
                    convo=gen.get("messages"),
                    metadata={"asta_sections": len(sections)},
                )
            )

        # Write ASTA-format output
        os.makedirs(self.output_dir, exist_ok=True)
        out_path = os.path.join(self.output_dir, "sqa_asta_format.jsonl")
        with open(out_path, "w") as f:
            json.dump(asta_rows, f, indent=2)
        logger.info("Wrote ASTA-format output to %s", out_path)

        return results
