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


def _find_claude() -> str:
    """Resolve full path to ``claude`` binary."""
    import shutil

    path = shutil.which("claude")
    if path:
        return path
    # Shell may see a different PATH — ask it.
    try:
        result = subprocess.run(
            ["which", "claude"], capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    # Common locations
    for candidate in [
        Path.home() / ".nvm" / "versions" / "node" / "v20.18.1" / "bin" / "claude",
        Path("/usr/local/bin/claude"),
        Path.home() / ".local" / "bin" / "claude",
    ]:
        if candidate.exists():
            return str(candidate)
    return "claude"  # fallback, hope for the best


CLAUDE_BIN = _find_claude()


def _parse_stream_json(raw: str) -> dict[str, Any]:
    """Parse stream-json (NDJSON) output into a structured result dict.

    Event format (from ``claude -p --output-format stream-json --verbose``):

    - ``{"type":"system","subtype":"init",...}`` — session init
    - ``{"type":"assistant","message":{"content":[...]}}`` — assistant turn
      Content blocks: ``{"type":"thinking",...}``, ``{"type":"text",...}``,
      ``{"type":"tool_use","name":...,"input":...}``
    - ``{"type":"tool_result",...}`` — tool execution result
    - ``{"type":"result","subtype":"success",...}`` — final summary
    """
    events: list[dict[str, Any]] = []
    result_msg: dict[str, Any] = {}

    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        events.append(event)

        if event.get("type") == "result":
            result_msg = event

    # Build trajectory — deduplicate assistant messages by uuid since
    # stream-json may emit multiple events for the same message as
    # content blocks arrive incrementally.
    seen_uuids: set[str] = set()
    trajectory: list[dict[str, Any]] = []

    for ev in events:
        ev_type = ev.get("type", "")

        if ev_type == "assistant" and "message" in ev:
            uuid = ev.get("uuid", "")
            if uuid in seen_uuids:
                continue
            seen_uuids.add(uuid)

            msg = ev["message"]
            for block in msg.get("content", []):
                block_type = block.get("type", "")
                if block_type == "text" and block.get("text"):
                    trajectory.append({
                        "type": "text",
                        "text": block["text"],
                    })
                elif block_type == "tool_use":
                    trajectory.append({
                        "type": "tool_use",
                        "name": block.get("name", ""),
                        "input": block.get("input", {}),
                    })
                elif block_type == "thinking" and block.get("thinking"):
                    trajectory.append({
                        "type": "thinking",
                        "text": block["thinking"][:1000],
                    })

        # Tool results appear as type="user" with a tool_use_result key.
        elif ev_type == "user" and "tool_use_result" in ev:
            result_data = ev["tool_use_result"]
            content = result_data if isinstance(result_data, str) else str(result_data)
            trajectory.append({
                "type": "tool_result",
                "content": content[:2000],
            })
        elif ev_type == "user" and "message" in ev:
            # Fallback: tool result may also be in message.content
            msg = ev["message"]
            content_blocks = msg.get("content", [])
            if isinstance(content_blocks, list):
                for block in content_blocks:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        c = block.get("content", "")
                        if isinstance(c, list):
                            c = "\n".join(
                                b.get("text", "") for b in c
                                if isinstance(b, dict) and b.get("type") == "text"
                            )
                        trajectory.append({
                            "type": "tool_result",
                            "content": str(c)[:2000],
                        })

    return {
        "result": result_msg.get("result", ""),
        "num_turns": result_msg.get("num_turns", 0),
        "total_cost_usd": result_msg.get("total_cost_usd", 0),
        "session_id": result_msg.get("session_id", ""),
        "is_error": result_msg.get("is_error", False),
        "subtype": result_msg.get("subtype", ""),
        "duration_ms": result_msg.get("duration_ms", 0),
        "usage": result_msg.get("usage", {}),
        "trajectory": trajectory,
    }


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
    """Run ``claude -p <prompt>`` and return the parsed result.

    Uses ``--output-format stream-json --verbose`` to capture the full
    conversation trajectory (tool calls, tool results, assistant text).

    Returns a dict with ``result``, ``trajectory``, ``num_turns``,
    ``total_cost_usd``, ``session_id``, etc.  On failure the dict
    contains an ``error`` key instead.
    """
    cmd: list[str] = [
        CLAUDE_BIN,
        "-p", prompt,
        "--output-format", "stream-json",
        "--verbose",
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
        return {"error": "timeout", "result": "", "trajectory": []}

    if proc.returncode != 0:
        stderr = proc.stderr.strip()[:500]
        logger.error("Exit %d: %s", proc.returncode, stderr)
        return {"error": f"exit_{proc.returncode}", "result": "",
                "stderr": stderr, "trajectory": []}

    data = _parse_stream_json(proc.stdout)

    logger.info("Done  turns=%d  cost=$%.4f  chars=%d  trajectory=%d events",
                data.get("num_turns", 0),
                data.get("total_cost_usd", 0),
                len(data.get("result", "")),
                len(data.get("trajectory", [])))
    return data
