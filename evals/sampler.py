"""Anthropic API sampler with tool-use loop.

Sends messages to Claude, executes tool calls via our CLI tools, and
loops until Claude produces a final text response or we hit max_turns.
"""

from __future__ import annotations

import logging
from typing import Any

import anthropic

from .tools import ALL_TOOLS, execute_tool
from .types import MessageList, SamplerResponse

logger = logging.getLogger(__name__)

DEFAULT_SYSTEM_PROMPT = """\
You are a research assistant with access to tools for reading academic papers \
and searching the web and academic databases.

Use the available tools to thoroughly answer the user's question. You can:
- Search for relevant papers using web_search, scholar_search, academic_search, \
snippet_search, or pubmed_search
- Browse specific URLs with browse_url
- Read papers with paper_read, paper_outline, paper_skim, paper_search, paper_info
- Navigate paper references with paper_goto

When answering research questions:
1. Search for relevant sources first
2. Read and analyze the most promising papers
3. Synthesize findings into a comprehensive answer with citations
"""


class AnthropicToolSampler:
    """Claude API client that executes tool calls in a loop."""

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        max_tokens: int = 16384,
        max_turns: int = 15,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
    ):
        self.client = anthropic.Anthropic()
        self.model = model
        self.system_prompt = system_prompt
        self.max_tokens = max_tokens
        self.max_turns = max_turns
        self.tools = tools or ALL_TOOLS
        self.temperature = temperature

    def __call__(self, message_list: MessageList) -> SamplerResponse:
        """Run the agentic tool-use loop.

        *message_list* should be a list of dicts with ``role`` and ``content``
        keys (the user prompt).  Returns a :class:`SamplerResponse` with the
        final text and full conversation trace.
        """
        messages: MessageList = list(message_list)
        all_tool_calls: list[dict[str, Any]] = []
        metadata: dict[str, Any] = {"turns": 0, "model": self.model}

        for turn in range(self.max_turns):
            metadata["turns"] = turn + 1

            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=self.system_prompt,
                tools=self.tools,
                messages=messages,
                temperature=self.temperature,
            )

            # Accumulate usage
            if response.usage:
                metadata.setdefault("input_tokens", 0)
                metadata.setdefault("output_tokens", 0)
                metadata["input_tokens"] += response.usage.input_tokens
                metadata["output_tokens"] += response.usage.output_tokens

            # Check if we got any tool_use blocks
            tool_use_blocks = [b for b in response.content if b.type == "tool_use"]

            if not tool_use_blocks:
                # Final text response — extract and return
                text_parts = [b.text for b in response.content if b.type == "text"]
                final_text = "\n".join(text_parts)
                messages.append({"role": "assistant", "content": final_text})
                return SamplerResponse(
                    response_text=final_text,
                    messages=messages,
                    tool_calls=all_tool_calls,
                    metadata=metadata,
                )

            # Build assistant message with all content blocks
            assistant_content: list[dict[str, Any]] = []
            for block in response.content:
                if block.type == "text":
                    assistant_content.append({"type": "text", "text": block.text})
                elif block.type == "tool_use":
                    assistant_content.append({
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    })
            messages.append({"role": "assistant", "content": assistant_content})

            # Execute each tool call and build tool_result blocks
            tool_results: list[dict[str, Any]] = []
            for block in tool_use_blocks:
                logger.info("Tool call: %s(%s)", block.name, block.input)
                output = execute_tool(block.name, block.input)
                logger.info("Tool result: %s chars", len(output))

                all_tool_calls.append({
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                    "output": output,
                })
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": output,
                })

            messages.append({"role": "user", "content": tool_results})

        # Exhausted max_turns — return whatever we have
        text_parts = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
        final_text = "\n".join(text_parts) if text_parts else "[max turns reached]"
        messages.append({"role": "assistant", "content": final_text})
        metadata["max_turns_reached"] = True

        return SamplerResponse(
            response_text=final_text,
            messages=messages,
            tool_calls=all_tool_calls,
            metadata=metadata,
        )
