"""Run ``claude -p`` and return structured results.

This is the only module that knows about the ``claude`` CLI.  Everything
else in the eval harness works with plain dicts.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Project root where CLAUDE.md lives.
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)


def run_claude(
    prompt: str,
    *,
    model: str = "sonnet",
    max_turns: int = 15,
    max_budget_usd: float | None = None,
    permission_mode: str = "bypassPermissions",
    cwd: str | None = None,
    timeout: int = 600,
    append_system_prompt: str | None = None,
) -> dict[str, Any]:
    """Run ``claude -p <prompt>`` and return the parsed JSON result.

    Returns a dict with at least ``result`` (the response text) plus
    ``num_turns``, ``total_cost_usd``, ``session_id``, etc.  On failure
    the dict contains an ``error`` key instead.
    """
    cmd: list[str] = [
        "claude",
        "-p", prompt,
        "--output-format", "json",
        "--model", model,
        "--max-turns", str(max_turns),
        "--no-session-persistence",
        "--permission-mode", permission_mode,
    ]

    if append_system_prompt:
        cmd.extend(["--append-system-prompt", append_system_prompt])
    if max_budget_usd is not None:
        cmd.extend(["--max-budget-usd", str(max_budget_usd)])

    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

    logger.info("claude -p  model=%s  max_turns=%d  prompt=%s…",
                model, max_turns, prompt[:80])

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=cwd or PROJECT_ROOT,
            env=env,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        logger.error("Timed out after %ds", timeout)
        return {"error": "timeout", "result": ""}

    if proc.returncode != 0:
        stderr = proc.stderr.strip()[:500]
        logger.error("Exit %d: %s", proc.returncode, stderr)
        return {"error": f"exit_{proc.returncode}", "result": "", "stderr": stderr}

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        logger.error("Bad JSON: %s", proc.stdout[:300])
        return {"error": "json_parse", "result": proc.stdout.strip()}

    logger.info("Done  turns=%d  cost=$%.4f  chars=%d",
                data.get("num_turns", 0),
                data.get("total_cost_usd", 0),
                len(data.get("result", "")))
    return data
