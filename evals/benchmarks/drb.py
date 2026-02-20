"""Deep Research Bench (DRB) benchmark: format converter for RACE/FACT scoring.

Generates research reports using our tools, then converts to DRB format
(article + citations + deduped URLs) for external evaluation.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from ..common import map_with_progress
from ..sampler import AnthropicToolSampler
from ..types import SingleEvalResult
from .base import Eval

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DRB format conversion (adapted from DR-Tulu drb_formatter.py)
# ---------------------------------------------------------------------------


def _parse_search_results(text: str) -> list[dict[str, str]]:
    """Parse Title/URL/Snippet blocks from tool output."""
    pattern = re.compile(
        r"Title: (.*?)\n"
        r"(?:URL: (.*?)\n)?"
        r"Snippet: (.*?)"
        r"(?=\nTitle: |\Z)",
        re.DOTALL,
    )
    results = []
    for m in pattern.finditer(text):
        results.append({
            "Title": m.group(1).strip(),
            "URL": (m.group(2) or "").strip(),
            "Snippet": m.group(3).strip(),
        })
    return results


def _parse_and_format_citations(text: str) -> tuple[str, list[str], dict[str, list[str]]]:
    """Parse <cite> tags, reformat to [id], and extract id -> text mapping."""
    citation_ids: list[str] = []
    id_to_text: dict[str, list[str]] = {}

    def replacer(match: re.Match) -> str:
        ids_str = match.group(1)
        text_content = match.group(2)
        ids = ids_str.split(",")
        for cid in ids:
            if cid not in citation_ids:
                citation_ids.append(cid)
            id_to_text.setdefault(cid, []).append(text_content)
        formatted = " ".join(f"[{cid}]" for cid in ids)
        return f". {text_content} {formatted}."

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

    # Build traces from tool calls
    traces: dict[str, dict[str, str]] = {}
    all_urls: dict[str, str] = {}

    for call in gen.get("tool_calls", []):
        call_id = call.get("id", "")
        call_results = _parse_search_results(call.get("output", ""))
        for i, result in enumerate(call_results):
            key = f"{call_id}-{i}"
            traces[key] = result
            if result["URL"]:
                all_urls[result["URL"]] = key

    # Parse citations from response
    response_text = gen.get("response_text", "")
    article, citation_ids, id_to_text = _parse_and_format_citations(response_text)

    # Map citations to URLs
    for url, cid in all_urls.items():
        if cid in id_to_text:
            output["citations_deduped"][url] = {
                "facts": id_to_text[cid],
                "url_content": traces[cid]["Title"] + "\n\n" + traces[cid]["Snippet"],
            }
            for fact in id_to_text[cid]:
                output["citations"].append({
                    "fact": fact,
                    "ref_indx": cid,
                    "url": url,
                })

    # Renumber citations and build references
    references = []
    for i, cid in enumerate(citation_ids):
        if cid in traces:
            references.append(f"[{i + 1}] {traces[cid]['URL']}")
            article = article.replace(cid, str(i + 1))
        else:
            # Try partial URL match
            found = False
            for url in all_urls:
                if cid in url:
                    references.append(f"[{i + 1}] {url}")
                    article = article.replace(cid, str(i + 1))
                    found = True
                    break
            if not found:
                article = article.replace(f"[{cid}]", "")

    # Detect Chinese content
    if re.search(r"[\u4e00-\u9fff]", article):
        output["article"] = article + "\n\n 参考文献: " + "\n".join(references)
    else:
        output["article"] = article + "\n\n References: " + "\n".join(references)

    return output


# ---------------------------------------------------------------------------
# Eval class
# ---------------------------------------------------------------------------


class DRBEval(Eval):
    """DRB evaluation — generates research reports and exports DRB-format JSONL."""

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

    def generate(self, sampler: AnthropicToolSampler) -> list[dict[str, Any]]:
        """Generate research reports for each DRB query."""

        def generate_single(item: dict[str, Any]) -> dict[str, Any]:
            query = item.get("problem") or item.get("query", "")
            prompt = [{"role": "user", "content": query}]
            response = sampler(prompt)
            return {
                "item": item,
                "response_text": response.response_text,
                "messages": response.messages,
                "tool_calls": response.tool_calls,
                "metadata": response.metadata,
            }

        return map_with_progress(
            generate_single, self.items, num_threads=self.n_threads
        )

    def evaluate(self, generation_data: list[dict[str, Any]]) -> list[SingleEvalResult]:
        """Convert to DRB format and save. Returns placeholder results.

        Actual RACE/FACT scoring is deferred to the external DRB evaluator.
        """
        drb_rows = []
        results = []

        for i, gen in enumerate(generation_data):
            try:
                formatted = _format_example(gen)
                drb_rows.append(formatted)
            except Exception:
                logger.error("Failed to format DRB example %d", i)
                formatted = {"id": str(i), "article": "", "citations": []}
                drb_rows.append(formatted)

            results.append(
                SingleEvalResult(
                    id=str(i),
                    score=None,
                    metrics={},
                    convo=gen.get("messages"),
                    metadata={"n_citations": len(formatted.get("citations", []))},
                )
            )

        # Write DRB-format output
        os.makedirs(self.output_dir, exist_ok=True)
        out_path = os.path.join(self.output_dir, "drb_format.jsonl")
        with open(out_path, "w") as f:
            for row in drb_rows:
                f.write(json.dumps(row) + "\n")
        logger.info("Wrote DRB-format output to %s", out_path)

        return results
