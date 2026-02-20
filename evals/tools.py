"""Tool definitions and CLI execution for the eval harness.

Each tool maps to a `paper` or `paper-search` CLI command.  The Anthropic
tool-use schema is defined here, and ``execute_tool`` dispatches to the right
subprocess call.
"""

from __future__ import annotations

import subprocess
from typing import Any

# ---------------------------------------------------------------------------
# Paper tools
# ---------------------------------------------------------------------------

PAPER_READ = {
    "name": "paper_read",
    "description": (
        "Read a paper or a specific section. "
        "REFERENCE is an arxiv ID, URL, or local PDF path. "
        "Optionally pass SECTION to read only that section."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "reference": {
                "type": "string",
                "description": "Arxiv ID, URL, or local PDF path.",
            },
            "section": {
                "type": "string",
                "description": "Section name to read (optional).",
            },
            "max_lines": {
                "type": "integer",
                "description": "Max lines to show. 0 for unlimited.",
            },
        },
        "required": ["reference"],
    },
}

PAPER_OUTLINE = {
    "name": "paper_outline",
    "description": "Show the outline / table of contents for a paper.",
    "input_schema": {
        "type": "object",
        "properties": {
            "reference": {
                "type": "string",
                "description": "Arxiv ID, URL, or local PDF path.",
            },
        },
        "required": ["reference"],
    },
}

PAPER_SKIM = {
    "name": "paper_skim",
    "description": (
        "Skim a paper: show headings and first N sentences per section."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "reference": {
                "type": "string",
                "description": "Arxiv ID, URL, or local PDF path.",
            },
            "lines": {
                "type": "integer",
                "description": "Sentences per section (default 2).",
            },
            "level": {
                "type": "integer",
                "description": "Max heading level to show.",
            },
        },
        "required": ["reference"],
    },
}

PAPER_SEARCH = {
    "name": "paper_search",
    "description": "Search for keywords inside a paper.",
    "input_schema": {
        "type": "object",
        "properties": {
            "reference": {
                "type": "string",
                "description": "Arxiv ID, URL, or local PDF path.",
            },
            "query": {
                "type": "string",
                "description": "Text to search for.",
            },
            "context": {
                "type": "integer",
                "description": "Lines of context around matches (default 2).",
            },
        },
        "required": ["reference", "query"],
    },
}

PAPER_INFO = {
    "name": "paper_info",
    "description": "Show metadata for a paper (title, sections, pages, etc.).",
    "input_schema": {
        "type": "object",
        "properties": {
            "reference": {
                "type": "string",
                "description": "Arxiv ID, URL, or local PDF path.",
            },
        },
        "required": ["reference"],
    },
}

PAPER_GOTO = {
    "name": "paper_goto",
    "description": (
        "Jump to a cross-reference shown in paper output. "
        "REF_ID examples: s3 (section), c5 (citation), f1 (figure), t2 (table), eq3 (equation)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "reference": {
                "type": "string",
                "description": "Arxiv ID, URL, or local PDF path.",
            },
            "ref_id": {
                "type": "string",
                "description": "Reference identifier (e.g. s3, f1, t2, eq3, c5).",
            },
        },
        "required": ["reference", "ref_id"],
    },
}

# ---------------------------------------------------------------------------
# Search tools
# ---------------------------------------------------------------------------

WEB_SEARCH = {
    "name": "web_search",
    "description": "Search the web via Google (Serper API).",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query."},
            "num": {
                "type": "integer",
                "description": "Number of results (default 10).",
            },
        },
        "required": ["query"],
    },
}

SCHOLAR_SEARCH = {
    "name": "scholar_search",
    "description": "Search Google Scholar.",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query."},
            "num": {
                "type": "integer",
                "description": "Number of results (default 10).",
            },
        },
        "required": ["query"],
    },
}

ACADEMIC_SEARCH = {
    "name": "academic_search",
    "description": (
        "Search for academic papers via Semantic Scholar. "
        "Supports year range, citation, venue, and sort filters."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query."},
            "year": {
                "type": "string",
                "description": "Year range, e.g. '2020-2024' or '2023-'.",
            },
            "min_citations": {
                "type": "integer",
                "description": "Minimum citation count.",
            },
            "venue": {
                "type": "string",
                "description": "Venue filter, e.g. 'ACL', 'NeurIPS'.",
            },
            "sort": {
                "type": "string",
                "description": "Sort order, e.g. 'citationCount:desc'.",
            },
            "limit": {
                "type": "integer",
                "description": "Number of results (default 10).",
            },
        },
        "required": ["query"],
    },
}

SNIPPET_SEARCH = {
    "name": "snippet_search",
    "description": "Search for text snippets across academic papers via Semantic Scholar.",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query."},
            "year": {
                "type": "string",
                "description": "Year range filter.",
            },
            "venue": {
                "type": "string",
                "description": "Venue filter.",
            },
            "limit": {
                "type": "integer",
                "description": "Number of snippets (default 10).",
            },
        },
        "required": ["query"],
    },
}

BROWSE_URL = {
    "name": "browse_url",
    "description": "Fetch and display webpage content.",
    "input_schema": {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "URL to browse."},
            "backend": {
                "type": "string",
                "enum": ["jina", "serper"],
                "description": "Content extraction backend (default jina).",
            },
        },
        "required": ["url"],
    },
}

PUBMED_SEARCH = {
    "name": "pubmed_search",
    "description": "Search PubMed for biomedical literature.",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query."},
            "limit": {
                "type": "integer",
                "description": "Number of results (default 10).",
            },
        },
        "required": ["query"],
    },
}

# ---------------------------------------------------------------------------
# All tools list
# ---------------------------------------------------------------------------

ALL_TOOLS: list[dict[str, Any]] = [
    PAPER_READ,
    PAPER_OUTLINE,
    PAPER_SKIM,
    PAPER_SEARCH,
    PAPER_INFO,
    PAPER_GOTO,
    WEB_SEARCH,
    SCHOLAR_SEARCH,
    ACADEMIC_SEARCH,
    SNIPPET_SEARCH,
    BROWSE_URL,
    PUBMED_SEARCH,
]


# ---------------------------------------------------------------------------
# CLI execution
# ---------------------------------------------------------------------------


def _run(cmd: list[str], timeout: int = 120) -> str:
    """Run a subprocess and return stdout, or stderr on failure."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            return f"[ERROR] {result.stderr.strip() or result.stdout.strip()}"
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        return "[ERROR] Command timed out."
    except FileNotFoundError:
        return f"[ERROR] Command not found: {cmd[0]}"


def execute_tool(name: str, input: dict[str, Any]) -> str:  # noqa: A002
    """Dispatch a tool call to the corresponding CLI command."""
    if name == "paper_read":
        cmd = ["paper", "--no-header", "read", input["reference"]]
        if input.get("section"):
            cmd.append(input["section"])
        if input.get("max_lines") is not None:
            cmd.extend(["--max-lines", str(input["max_lines"])])
        cmd.append("--no-refs")
        return _run(cmd)

    if name == "paper_outline":
        cmd = ["paper", "--no-header", "outline", input["reference"], "--no-refs"]
        return _run(cmd)

    if name == "paper_skim":
        cmd = ["paper", "--no-header", "skim", input["reference"]]
        if input.get("lines") is not None:
            cmd.extend(["--lines", str(input["lines"])])
        if input.get("level") is not None:
            cmd.extend(["--level", str(input["level"])])
        cmd.append("--no-refs")
        return _run(cmd)

    if name == "paper_search":
        cmd = [
            "paper", "--no-header", "search",
            input["reference"], input["query"],
        ]
        if input.get("context") is not None:
            cmd.extend(["--context", str(input["context"])])
        cmd.append("--no-refs")
        return _run(cmd)

    if name == "paper_info":
        cmd = ["paper", "--no-header", "info", input["reference"], "--no-refs"]
        return _run(cmd)

    if name == "paper_goto":
        cmd = ["paper", "goto", input["reference"], input["ref_id"]]
        return _run(cmd)

    if name == "web_search":
        cmd = ["paper-search", "google", "web", input["query"]]
        if input.get("num") is not None:
            cmd.extend(["--num", str(input["num"])])
        return _run(cmd)

    if name == "scholar_search":
        cmd = ["paper-search", "google", "scholar", input["query"]]
        if input.get("num") is not None:
            cmd.extend(["--num", str(input["num"])])
        return _run(cmd)

    if name == "academic_search":
        cmd = ["paper-search", "semanticscholar", "papers", input["query"]]
        for opt in ("year", "venue", "sort"):
            if input.get(opt):
                cmd.extend([f"--{opt}", input[opt]])
        if input.get("min_citations") is not None:
            cmd.extend(["--min-citations", str(input["min_citations"])])
        if input.get("limit") is not None:
            cmd.extend(["--limit", str(input["limit"])])
        return _run(cmd)

    if name == "snippet_search":
        cmd = ["paper-search", "semanticscholar", "snippets", input["query"]]
        for opt in ("year", "venue"):
            if input.get(opt):
                cmd.extend([f"--{opt}", input[opt]])
        if input.get("limit") is not None:
            cmd.extend(["--limit", str(input["limit"])])
        return _run(cmd)

    if name == "browse_url":
        cmd = ["paper-search", "browse", input["url"]]
        if input.get("backend"):
            cmd.extend(["--backend", input["backend"]])
        return _run(cmd)

    if name == "pubmed_search":
        cmd = ["paper-search", "pubmed", input["query"]]
        if input.get("limit") is not None:
            cmd.extend(["--limit", str(input["limit"])])
        return _run(cmd)

    return f"[ERROR] Unknown tool: {name}"
