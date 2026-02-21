"""Convert our eval output to DR-Tulu compatible format.

DR-Tulu's scoring scripts (DRB RACE/FACT, SQA ASTA) expect a specific
generation format with ``full_traces``, ``final_response``, and structured
``tool_calls``.  This module bridges the gap between our Claude Code
stream-json trajectory and that format.

Key DR-Tulu fields::

    {
        "example_id": "42",
        "problem": "...",
        "final_response": "... <cite id=\"r1\">claim</cite> ...",
        "full_traces": {
            "generated_text": "...",      # raw generation with tool calls
            "tool_calls": [               # structured tool call records
                {
                    "call_id": "r1",
                    "tool_name": "web_search",
                    "query": "...",
                    "output": "Title: ...\\nURL: ...\\nSnippet: ...",
                    "generated_text": "<snippet id=r1>...</snippet>",
                },
            ],
            "tool_call_count": 4,
            "total_tokens": 12377,
        },
    }
"""

from __future__ import annotations

import re
from typing import Any


# ---------------------------------------------------------------------------
# Parse search result text into structured records
# ---------------------------------------------------------------------------

_REF_PATTERN = re.compile(
    r"\[([a-z0-9][\w-]*)\]\s+"    # [r1], [ddd5f455], [abc12345-1], etc.
    r"(.+?)\n"                     # title line
    r"(?:\s+(\S+)\n)?"            # optional URL line (indented)
    r"([\s\S]*?)"                  # body (snippet, metadata, etc.)
    r"(?=\n\[(?:[a-z0-9][\w-]*)\]|\Z)",  # lookahead: next result or end
    re.MULTILINE,
)


def parse_search_results(text: str) -> dict[str, dict[str, str]]:
    """Parse tool result text into ``{ref_id: {title, url, snippet}}`` map.

    Handles output from ``paper-search google web``, ``paper-search
    semanticscholar papers``, ``paper-search semanticscholar snippets``, etc.

    Example input::

        [r1] Attention is All you Need
             https://www.semanticscholar.org/paper/...
             Ashish Vaswani, ... | 2017 | ...
             The dominant sequence transduction models are based on ...
    """
    results: dict[str, dict[str, str]] = {}

    # Try structured regex first
    for match in _REF_PATTERN.finditer(text):
        ref_id = match.group(1)
        title = match.group(2).strip()
        url = (match.group(3) or "").strip()
        body = (match.group(4) or "").strip()

        # If "url" doesn't look like a URL, it's part of the body
        if url and not url.startswith(("http://", "https://")):
            body = url + "\n" + body
            url = ""

        # Try to extract URL from body lines
        if not url:
            for line in body.split("\n"):
                line = line.strip()
                if line.startswith(("http://", "https://")):
                    url = line
                    break

        # Extract snippet from body (everything after metadata lines)
        snippet_lines = []
        for line in body.split("\n"):
            line = line.strip()
            if not line:
                continue
            # Skip metadata lines (author | year | venue | cited by)
            if re.match(r".+\|.*\d{4}", line):
                continue
            # Skip suggestive prompts
            if line.startswith("> Use `"):
                continue
            # Skip section/type/score metadata
            if re.match(r"section:.*\|.*type:.*\|.*score:", line):
                continue
            snippet_lines.append(line)

        results[ref_id] = {
            "Title": title,
            "URL": url,
            "Snippet": " ".join(snippet_lines),
        }

    return results


# ---------------------------------------------------------------------------
# Convert our trajectory to DR-Tulu full_traces
# ---------------------------------------------------------------------------


def _pair_tool_events(trajectory: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Pair consecutive tool_use + tool_result events from our trajectory."""
    calls: list[dict[str, Any]] = []
    i = 0
    while i < len(trajectory):
        ev = trajectory[i]
        if ev.get("type") == "tool_use":
            call: dict[str, Any] = {
                "tool_name": ev.get("name", ""),
                "query": _extract_query(ev),
                "output": "",
                "generated_text": "",
            }
            # Look for the matching tool_result
            if i + 1 < len(trajectory) and trajectory[i + 1].get("type") == "tool_result":
                call["output"] = trajectory[i + 1].get("content", "")
            calls.append(call)
        i += 1
    return calls


def _extract_query(tool_use_event: dict[str, Any]) -> str:
    """Extract the user's query from a tool_use event."""
    inp = tool_use_event.get("input", {})
    if isinstance(inp, dict):
        # paper-search commands use "query" or first positional arg
        return (
            inp.get("query", "")
            or inp.get("command", "")
            or inp.get("url", "")
            or str(inp)
        )
    return str(inp)


def build_full_traces(
    trajectory: list[dict[str, Any]],
    usage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Convert our trajectory to DR-Tulu ``full_traces`` dict.

    Returns a dict with ``tool_calls``, ``tool_call_count``, ``total_tokens``,
    and ``generated_text`` (reconstructed from trajectory events).
    """
    raw_calls = _pair_tool_events(trajectory)

    # Assign call_ids by parsing reference IDs from each tool result.
    # If a tool result contains [r1], [r2], etc., we use those as sub-IDs.
    tool_calls: list[dict[str, Any]] = []
    for idx, call in enumerate(raw_calls):
        output_text = call["output"]
        parsed = parse_search_results(output_text)

        # Build snippet-format generated_text for DR-Tulu compatibility
        snippet_parts = []
        for ref_id, info in parsed.items():
            snippet_parts.append(
                f'<snippet id={ref_id}>\n'
                f'Title: {info["Title"]}\n'
                f'URL: {info["URL"]}\n'
                f'Snippet: {info["Snippet"]}\n'
                f'</snippet>'
            )

        call_id = f"call_{idx}"
        tool_calls.append({
            "call_id": call_id,
            "tool_name": call["tool_name"],
            "query": call["query"],
            "output": output_text,
            "generated_text": "\n".join(snippet_parts),
            # Flatten parsed results with call_id-based sub-IDs for
            # backwards compat, but also keep original ref_ids
            "parsed_results": parsed,
        })

    # Reconstruct generated_text (rough approximation of the full trace)
    parts: list[str] = []
    for ev in trajectory:
        t = ev.get("type", "")
        if t == "thinking":
            parts.append(f'<think>{ev.get("text", "")}</think>')
        elif t == "text":
            parts.append(ev.get("text", ""))
        elif t == "tool_use":
            name = ev.get("name", "")
            query = _extract_query(ev)
            parts.append(f'<call_tool name="{name}">{query}</call_tool>')
        elif t == "tool_result":
            content = ev.get("content", "")
            parts.append(f"<tool_output>{content}</tool_output>")

    usage = usage or {}
    return {
        "generated_text": "\n".join(parts),
        "tool_calls": tool_calls,
        "tool_call_count": len(tool_calls),
        "total_tokens": usage.get("total_tokens", 0),
        "stopped_reason": "natural",
    }


# ---------------------------------------------------------------------------
# Build ref_id → snippet mapping from full_traces
# ---------------------------------------------------------------------------


def build_snippet_map(full_traces: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Build a mapping from reference IDs to ``{Title, URL, Snippet}`` dicts.

    Merges all ``parsed_results`` from each tool call.  This is the primary
    lookup used by DRB and SQA formatters to resolve citations to URLs.
    """
    snippets: dict[str, dict[str, str]] = {}
    for call in full_traces.get("tool_calls", []):
        parsed = call.get("parsed_results", {})
        snippets.update(parsed)
    return snippets


def extract_snippet_text(full_traces: dict[str, Any]) -> str:
    """Concatenate all snippet-format generated_text from tool calls.

    Used by SQA's ASTA converter to extract citation content via
    ``extract_citations_from_context()``.
    """
    parts = []
    for call in full_traces.get("tool_calls", []):
        gt = call.get("generated_text", "")
        if gt:
            parts.append(gt)
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Top-level conversion: our gen dict → DR-Tulu gen dict
# ---------------------------------------------------------------------------


def to_drtulu_format(gen: dict[str, Any]) -> dict[str, Any]:
    """Convert a single generation row to DR-Tulu compatible format.

    Accepts our gen dict (with ``claude``, ``response_text``, etc.) and
    returns a dict with ``final_response``, ``full_traces``, ``example_id``,
    and ``problem``.
    """
    claude = gen.get("claude", {})
    trajectory = claude.get("trajectory", [])
    usage = claude.get("usage", {})

    # Extract example_id from various possible locations
    example_id = (
        gen.get("item_id")
        or gen.get("item", {}).get("id", "")
        or gen.get("row", {}).get("id", "")
        or ""
    )

    problem = (
        gen.get("query")
        or gen.get("question")
        or gen.get("item", {}).get("problem", "")
        or gen.get("item", {}).get("query", "")
        or ""
    )

    return {
        "example_id": str(example_id),
        "problem": problem,
        "final_response": gen.get("response_text", "") or claude.get("result", ""),
        "full_traces": build_full_traces(trajectory, usage),
    }
