"""Environment variable configuration for search backends.

API keys are loaded from environment variables or a .env file.
Run `search env` to see which keys are configured.

Required keys per command:
    search google web/scholar  ->  SERPER_API_KEY
    search semanticscholar *   ->  S2_API_KEY (optional but recommended for higher rate limits)
    search pubmed              ->  (no key needed)
    search browse --backend jina   ->  JINA_API_KEY
    search browse --backend serper ->  SERPER_API_KEY
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from current directory or parents
load_dotenv()

# Also try loading from ~/.env as a fallback for global keys
_home_env = Path.home() / ".env"
if _home_env.exists():
    load_dotenv(_home_env)


# --- API key accessors ---

def get_serper_key() -> str:
    key = os.getenv("SERPER_API_KEY", "")
    if not key:
        raise ValueError(
            "SERPER_API_KEY is not set. "
            "Export it or add it to a .env file in the current directory."
        )
    return key


def get_s2_key() -> str | None:
    """S2 key is optional — returns None if not set."""
    return os.getenv("S2_API_KEY") or None


def get_jina_key() -> str:
    key = os.getenv("JINA_API_KEY", "")
    if not key:
        raise ValueError(
            "JINA_API_KEY is not set. "
            "Export it or add it to a .env file in the current directory."
        )
    return key


# --- Status check ---

ENV_VARS = {
    "SERPER_API_KEY": {
        "required_by": ["search google", "search browse --backend serper"],
        "description": "Google search and scraping via Serper.dev",
    },
    "S2_API_KEY": {
        "required_by": ["search semanticscholar (optional, increases rate limits)"],
        "description": "Semantic Scholar academic paper API",
    },
    "JINA_API_KEY": {
        "required_by": ["search browse --backend jina"],
        "description": "Jina Reader for webpage content extraction",
    },
}


def check_env() -> list[tuple[str, bool, dict]]:
    """Return list of (var_name, is_set, info) for all known env vars."""
    result = []
    for var, info in ENV_VARS.items():
        is_set = bool(os.getenv(var))
        result.append((var, is_set, info))
    return result
