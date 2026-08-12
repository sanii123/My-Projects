"""Thin async client for Ollama's /api/chat. docs/architecture.md section 4.4.

Kept behind this interface (not called directly from app.runtime) so
swapping models - or swapping in a hosted API as a fallback later - is a
config change here, not a rewrite of the Agent Runtime.
"""

from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("llm")


class OllamaError(Exception):
    """Raised when Ollama is unreachable, times out, or returns a non-2xx."""


class OllamaClient:
    def __init__(self, base_url: str | None = None, model: str | None = None) -> None:
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.model = model or settings.ollama_model

    async def chat(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        """One non-streaming turn. Returns Ollama's `message` object:
        {"role": "assistant", "content": str, "tool_calls": [...] | None}.

        Non-streaming on purpose here: the tool-call loop in
        app/runtime/agent.py needs the complete tool_calls array before it can
        decide what to dispatch. Verify the exact tool_call wire shape against
        whichever model you land on (section 11) - it varies enough between
        models that this is worth testing before trusting it in production.
        """
        payload: dict[str, Any] = {"model": self.model, "messages": messages, "stream": False}
        if tools:
            payload["tools"] = tools

        try:
            async with httpx.AsyncClient(timeout=settings.agent_turn_timeout_seconds) as client:
                resp = await client.post(f"{self.base_url}/api/chat", json=payload)
                resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("ollama.unavailable", error=str(exc))
            raise OllamaError(f"Ollama request failed: {exc}") from exc

        return resp.json()["message"]
