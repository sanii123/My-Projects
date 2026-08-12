"""Tool registry + the normalized result contract. docs/architecture.md 4.5.

Every adapter - read or write - returns a ToolResult, so the model gets a
consistent shape regardless of which backend endpoint answered.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.core.security import UserContext


@dataclass
class ToolResult:
    success: bool
    data: Any = None
    summary: str = ""
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"success": self.success, "data": self.data, "summary": self.summary, "error": self.error}


ToolHandler = Callable[[dict[str, Any], UserContext], Awaitable[ToolResult]]


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON schema, handed to the LLM as-is
    handler: ToolHandler
    is_write: bool = False
    retryable: bool = True  # reads only - writes must never auto-retry (section 6)


class ToolRegistry:
    """Holds every tool; filters by permission before schemas ever reach the LLM.

    docs/architecture.md 4.3: "the runtime should not expose write tools to a
    read-only user, full stop" - enforced here, once, rather than per-adapter.
    """

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def schemas_for(self, user: UserContext) -> list[dict[str, Any]]:
        """Ollama/OpenAI-style tool schema: {"type": "function", "function": {...}}."""
        visible = (
            self._tools.values()
            if user.can_write
            else (t for t in self._tools.values() if not t.is_write)
        )
        return [
            {
                "type": "function",
                "function": {"name": t.name, "description": t.description, "parameters": t.parameters},
            }
            for t in visible
        ]

    async def execute(self, name: str, arguments: dict[str, Any], user: UserContext) -> ToolResult:
        tool = self.get(name)
        if tool is None:
            return ToolResult(success=False, error=f"Unknown tool: {name}")
        if tool.is_write and not user.can_write:
            return ToolResult(success=False, error="Write access required for this tool")
        return await tool.handler(arguments, user)


registry = ToolRegistry()
