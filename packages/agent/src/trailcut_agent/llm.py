"""Claude adapter for the agent team (Messages API, manual tool loop in ``team.py``).

The loop is hand-written rather than the SDK tool runner because every answer must
pass the numeric-claim validator, and tool calls, rounds and wall-clock time are
capped (CLAUDE.md agent rules).

Example:
    >>> llm = ClaudeLLM(api_key="...")  # doctest: +SKIP
"""

from __future__ import annotations

from typing import Any, cast

import anthropic

DEFAULT_MODEL = "claude-opus-5-5"
REQUEST_TIMEOUT_SECONDS = 20.0
MAX_TOKENS = 16000


class ClaudeLLM:
    """One Messages API call per round; the system prompt is cached across rounds."""

    def __init__(self, *, api_key: str | None, model: str = DEFAULT_MODEL) -> None:
        # A missing key falls back to the SDK's own credential lookup.
        self.client = anthropic.Anthropic(
            api_key=api_key, timeout=REQUEST_TIMEOUT_SECONDS, max_retries=1
        )
        self.model = model

    def create(
        self, *, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> object:
        # The team builds plain-dict messages in the API's wire shape; the SDK's TypedDict
        # overloads can't see that statically.
        messages_api = cast(Any, self.client.beta.messages)
        return messages_api.create(
            model=self.model,
            max_tokens=MAX_TOKENS,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=messages,
            tools=tools,
            output_config={"effort": "medium"},
            # If a safety classifier declines, the API re-runs the request on a fallback model.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
