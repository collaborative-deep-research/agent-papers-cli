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
                "input": ev.get("input", {}),
                "output": "",
            }
            # Look for the matching tool_result
            if i + 1 < len(trajectory) and trajectory[i + 1].get("type") == "tool_result":
                call["output"] = trajectory[i + 1].get("content", "")
            calls.append(call)
        i += 1
    return calls


# Maps CLI subcommands to DR-Tulu tool names.
_TOOL_NAME_MAP: dict[str, str] = {
    "google web": "google_search",
    "google scholar": "google_search",
    "semanticscholar papers": "snippet_search",
    "semanticscholar snippets": "snippet_search",
    "semanticscholar citations": "snippet_search",
    "semanticscholar references": "snippet_search",
    "pubmed": "pubmed_search",
    "browse": "browse_webpage",
}


def _classify_tool_call(raw: dict[str, Any]) -> tuple[str, str]:
    """Return ``(tool_name, query)`` by inspecting the Bash command.

    Parses ``paper-search <backend> <subcommand> "query"`` to extract the
    DR-Tulu compatible tool name and the user's search query.
    """
    inp = raw.get("input", {})
    cmd = inp.get("command", "") if isinstance(inp, dict) else str(inp)

    # Extract quoted query from command
    query_match = re.search(r'''['"]([^'"]+)['"]''', cmd)
    query = query_match.group(1) if query_match else cmd

    # Detect tool type from command
    for pattern, name in _TOOL_NAME_MAP.items():
        if pattern in cmd:
            return name, query

    # paper read / paper outline / other tools
    if "paper " in cmd and "paper-search" not in cmd:
        return "paper_read", query

    return raw.get("tool_name", "unknown"), query


def _build_tool_call(idx: int, raw: dict[str, Any]) -> dict[str, Any]:
    """Convert a single paired tool_use/tool_result into DR-Tulu format.

    Produces::

        {
            "tool_name": "google_search",
            "call_id": "bcd6aec2",
            "query": "transformer attention mechanism",
            "called": true,
            "output": "Title: ...\\nURL: ...\\nSnippet: ...\\n\\nTitle: ...",
            "documents": [{id, title, url, snippet, ...}, ...],
            "generated_text": "<snippet id=...>...</snippet>...",
            "parsed_results": {ref_id: {Title, URL, Snippet}},
        }
    """
    tool_name, query = _classify_tool_call(raw)
    output_text = raw["output"]
    parsed = parse_search_results(output_text)

    # Build documents array (DR-Tulu schema)
    documents: list[dict[str, Any]] = []
    for ref_id, info in parsed.items():
        documents.append({
            "id": ref_id,
            "title": info["Title"],
            "url": info["URL"],
            "snippet": info["Snippet"],
            "text": None,
            "summary": None,
            "score": None,
            "error": None,
        })

    # Build DR-Tulu style output (Title:\nURL:\nSnippet:\n format)
    drtulu_output_parts = []
    for info in parsed.values():
        lines = [f"Title: {info['Title']}"]
        if info["URL"]:
            lines.append(f"URL: {info['URL']}")
        lines.append(f"Snippet: {info['Snippet']}")
        drtulu_output_parts.append("\n".join(lines))
    drtulu_output = "\n\n".join(drtulu_output_parts)

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

    # Use first document's hash as call_id if available, else fallback
    call_id = documents[0]["id"] if documents else f"call_{idx}"

    return {
        "tool_name": tool_name,
        "call_id": call_id,
        "query": query,
        "called": True,
        "timeout": False,
        "error": "",
        "output": drtulu_output,
        "documents": documents,
        "generated_text": "\n".join(snippet_parts),
        "parsed_results": parsed,
        "raw_output_text": output_text,
    }


def build_full_traces(
    trajectory: list[dict[str, Any]],
    usage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Convert our trajectory to DR-Tulu ``full_traces`` dict.

    Returns a dict with ``tool_calls``, ``tool_call_count``, ``total_tokens``,
    and ``generated_text`` (reconstructed from trajectory events).
    """
    raw_calls = _pair_tool_events(trajectory)
    tool_calls = [_build_tool_call(i, c) for i, c in enumerate(raw_calls)]

    # Reconstruct generated_text (rough approximation of the full trace)
    parts: list[str] = []
    for ev in trajectory:
        t = ev.get("type", "")
        if t == "thinking":
            parts.append(f'<think>{ev.get("text", "")}</think>')
        elif t == "text":
            parts.append(ev.get("text", ""))
        elif t == "tool_use":
            name, query = _classify_tool_call(ev)
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
# Answer extraction
# ---------------------------------------------------------------------------

_ANSWER_RE = re.compile(r"<answer>(.*?)</answer>", re.DOTALL)


def extract_final_response(gen: dict[str, Any]) -> str:
    """Extract the best final response text from a generation dict.

    Search order:
    1. ``<answer>`` tags in ``response_text`` / ``claude.result``
    2. ``<answer>`` tags in trajectory text events (scanned last-to-first,
       since the final answer is typically the last one)
    3. Full ``response_text`` as-is (fallback)

    When ``<answer>`` tags are found the *inner* content is returned
    (stripped of the tags themselves).
    """
    # Candidate texts — check the top-level fields first.
    response_text = gen.get("response_text", "") or ""
    claude = gen.get("claude", {})
    result_text = claude.get("result", "") or ""

    for text in (response_text, result_text):
        m = _ANSWER_RE.search(text)
        if m:
            return m.group(1).strip()

    # Scan trajectory text events (last → first) for <answer> tags.
    trajectory = claude.get("trajectory", [])
    for ev in reversed(trajectory):
        if ev.get("type") == "text":
            m = _ANSWER_RE.search(ev.get("text", ""))
            if m:
                return m.group(1).strip()

    # No <answer> tags found anywhere — concatenate all trajectory text
    # events as a richer fallback than the (often-summarised) result field.
    text_parts = [
        ev.get("text", "")
        for ev in trajectory
        if ev.get("type") == "text" and ev.get("text")
    ]
    if text_parts:
        full_text = "\n\n".join(text_parts)
        # One more check on the concatenated text
        m = _ANSWER_RE.search(full_text)
        if m:
            return m.group(1).strip()
        # Prefer the longer of concatenated-text vs response_text
        if len(full_text) > len(response_text):
            return full_text

    return response_text or result_text


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
        "final_response": extract_final_response(gen),
        "full_traces": build_full_traces(trajectory, usage),
    }
