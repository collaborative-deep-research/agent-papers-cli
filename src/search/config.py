"""Environment variable configuration for search backends.

API keys are loaded in priority order:
  1. Shell environment variables (highest priority)
  2. .env file in current directory
  3. ~/.papers/.env (persistent config, set via `search env set`)

Run `search env` to see which keys are configured.
Run `search env set KEY value` to save a key persistently.

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

# Persistent config location (shared with paper CLI)
PAPERS_DIR = Path.home() / ".papers"
PERSISTENT_ENV = PAPERS_DIR / ".env"

# Load in reverse priority order (later loads don't overwrite existing)
# 1. ~/.papers/.env (lowest priority — persistent defaults)
if PERSISTENT_ENV.exists():
    load_dotenv(PERSISTENT_ENV)

# 2. .env in current directory (mid priority)
load_dotenv()

# 3. Shell env vars already set (highest priority — dotenv won't overwrite)


# --- Persistent config ---

def save_key(name: str, value: str) -> Path:
    """Save an API key to ~/.papers/.env for persistent use."""
    PAPERS_DIR.mkdir(parents=True, exist_ok=True)

    # Read existing entries
    lines: list[str] = []
    replaced = False
    if PERSISTENT_ENV.exists():
        for line in PERSISTENT_ENV.read_text().splitlines():
            if line.startswith(f"{name}="):
                lines.append(f"{name}={value}")
                replaced = True
            else:
                lines.append(line)

    if not replaced:
        lines.append(f"{name}={value}")

    PERSISTENT_ENV.write_text("\n".join(lines) + "\n")

    # Also set in current process
    os.environ[name] = value

    return PERSISTENT_ENV


# --- API key accessors ---

def get_serper_key() -> str:
    key = os.getenv("SERPER_API_KEY", "")
    if not key:
        raise ValueError(
            "SERPER_API_KEY is not set. "
            "Run `search env set SERPER_API_KEY <your-key>` to configure it."
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
            "Run `search env set JINA_API_KEY <your-key>` to configure it."
        )
    return key


# --- Status check ---

VALID_KEYS = {"SERPER_API_KEY", "S2_API_KEY", "JINA_API_KEY"}

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
