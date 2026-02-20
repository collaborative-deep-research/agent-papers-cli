"""Claude Code sampler — runs ``claude -p`` for each eval prompt.

Spawns the ``claude`` CLI in print mode with JSON output, letting Claude Code
use its full tool set (Bash, Read, Write, WebSearch, etc.) to call
``paper`` and ``paper-search`` commands.  The project's CLAUDE.md is
automatically loaded, giving Claude knowledge of the available CLI tools.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any

from .types import MessageList, SamplerResponse

logger = logging.getLogger(__name__)

# Resolve the project root (where CLAUDE.md lives) so that `claude -p` picks
# it up regardless of where the eval runner is invoked from.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_SYSTEM_PROMPT = """\
You are being evaluated on your ability to answer research questions.

Use the `paper` and `paper-search` CLI tools (via Bash) to find, read, and \
synthesize information from academic papers and the web.  Provide a thorough, \
well-cited answer.  Do NOT create or edit any files — just output your answer.\
"""


class ClaudeCodeSampler:
    """Run ``claude -p`` to generate a response with full tool access."""

    def __init__(
        self,
        model: str = "sonnet",
        system_prompt: str | None = DEFAULT_SYSTEM_PROMPT,
        max_turns: int = 15,
        max_budget_usd: float | None = None,
        permission_mode: str = "bypassPermissions",
        allowed_tools: list[str] | None = None,
        cwd: str | os.PathLike | None = None,
        timeout: int = 600,
    ):
        self.model = model
        self.system_prompt = system_prompt
        self.max_turns = max_turns
        self.max_budget_usd = max_budget_usd
        self.permission_mode = permission_mode
        self.allowed_tools = allowed_tools
        self.cwd = str(cwd or _PROJECT_ROOT)
        self.timeout = timeout

    # ------------------------------------------------------------------

    @staticmethod
    def _format_prompt(message_list: MessageList) -> str:
        """Convert a message list into a single prompt string for ``-p``."""
        if len(message_list) == 1:
            return message_list[0]["content"]

        # Multi-turn (e.g. HealthBench): format conversation, keep the
        # final user message as the actual prompt.
        parts: list[str] = []
        for msg in message_list[:-1]:
            role = msg["role"].capitalize()
            parts.append(f"{role}: {msg['content']}")
        history = "\n\n".join(parts)
        final = message_list[-1]["content"]
        return (
            f"<conversation_history>\n{history}\n</conversation_history>\n\n"
            f"{final}"
        )

    # ------------------------------------------------------------------

    def __call__(self, message_list: MessageList) -> SamplerResponse:
        prompt = self._format_prompt(message_list)

        cmd: list[str] = [
            "claude",
            "-p", prompt,
            "--output-format", "json",
            "--model", self.model,
            "--max-turns", str(self.max_turns),
            "--no-session-persistence",
            "--permission-mode", self.permission_mode,
        ]

        if self.system_prompt:
            cmd.extend(["--append-system-prompt", self.system_prompt])
        if self.max_budget_usd is not None:
            cmd.extend(["--max-budget-usd", str(self.max_budget_usd)])
        if self.allowed_tools:
            cmd.extend(["--allowedTools", ",".join(self.allowed_tools)])

        # Strip the CLAUDECODE env var so nested invocation is allowed.
        env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

        logger.info("Running: claude -p (model=%s, max_turns=%d)", self.model, self.max_turns)
        logger.debug("Prompt: %s", prompt[:200])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.cwd,
                env=env,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired:
            logger.error("claude -p timed out after %ds", self.timeout)
            return SamplerResponse(
                response_text="[ERROR] claude -p timed out",
                messages=message_list,
                metadata={"error": "timeout", "timeout": self.timeout},
            )

        if result.returncode != 0:
            stderr = result.stderr.strip()
            logger.error("claude -p failed (rc=%d): %s", result.returncode, stderr[:500])
            return SamplerResponse(
                response_text=f"[ERROR] claude -p exited {result.returncode}: {stderr[:500]}",
                messages=message_list,
                metadata={"error": "nonzero_exit", "returncode": result.returncode},
            )

        # Parse JSON output
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            logger.error("Failed to parse claude JSON output: %s", result.stdout[:500])
            return SamplerResponse(
                response_text=result.stdout.strip() or "[ERROR] empty output",
                messages=message_list,
                metadata={"error": "json_parse"},
            )

        response_text = data.get("result", "")
        metadata: dict[str, Any] = {
            "model": self.model,
            "num_turns": data.get("num_turns"),
            "duration_ms": data.get("duration_ms"),
            "duration_api_ms": data.get("duration_api_ms"),
            "total_cost_usd": data.get("total_cost_usd"),
            "session_id": data.get("session_id"),
            "is_error": data.get("is_error", False),
            "usage": data.get("usage"),
            "model_usage": data.get("modelUsage"),
        }

        messages = message_list + [{"role": "assistant", "content": response_text}]

        logger.info(
            "Done: %d turns, $%.4f, %d chars",
            data.get("num_turns", 0),
            data.get("total_cost_usd", 0),
            len(response_text),
        )

        return SamplerResponse(
            response_text=response_text,
            messages=messages,
            metadata=metadata,
        )
