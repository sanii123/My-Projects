"""Agent Runtime - the orchestration loop. docs/architecture.md sections 3 and 4.3.

A plain Python loop on purpose (see 4.3): send to the LLM, parse a tool call
if there is one, validate + dispatch it, feed the result back, repeat until
a final answer or the step limit. No agent framework.
"""

import asyncio
import json
import time
import uuid
from collections.abc import AsyncGenerator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.core.metrics import TOOL_CALL_TOTAL
from app.core.security import UserContext
from app.db.models.message import Message, MessageRole
from app.db.models.pending_action import PendingAction
from app.db.models.tool_call import ToolCall, ToolCallStatus
from app.llm.ollama_client import OllamaClient, OllamaError
from app.runtime.prompts import SYSTEM_PROMPT
from app.tools import read_tools, write_tools  # noqa: F401 - import side effect: registers tools
from app.tools.base import ToolResult, registry

logger = get_logger("runtime")

HISTORY_LIMIT = 20  # most recent messages; replace with real summarization once history grows (4.3)
READ_RETRY_ATTEMPTS = 3
READ_RETRY_BASE_DELAY_SECONDS = 0.5


class AgentRuntime:
    def __init__(self) -> None:
        self.llm = OllamaClient()

    async def handle_turn(
        self, *, session_id: uuid.UUID, user: UserContext, db: AsyncSession
    ) -> AsyncGenerator[str, None]:
        """Runs the full tool-call loop for one user turn, persists the
        assistant's final message, then yields it back in chunks for SSE.

        The chunking at the end is a simplification, not real token
        streaming from Ollama - see the comment near the bottom. The tool
        loop itself is not streamed; it needs each complete response to
        decide whether the model asked for a tool.
        """
        messages = await self._build_context(session_id, db)
        tool_schemas = registry.schemas_for(user)

        final_content = ""
        for _step in range(settings.agent_tool_step_limit):
            try:
                assistant_msg = await self.llm.chat(messages, tools=tool_schemas)
            except OllamaError as exc:
                logger.error("runtime.llm_unavailable", session_id=str(session_id), error=str(exc))
                final_content = "The assistant is temporarily unavailable. Please try again shortly."
                break

            tool_calls = assistant_msg.get("tool_calls") or []
            if not tool_calls:
                final_content = assistant_msg.get("content", "")
                break

            assistant_row = Message(
                session_id=session_id, role=MessageRole.ASSISTANT, content=assistant_msg.get("content") or ""
            )
            db.add(assistant_row)
            await db.flush()

            messages.append(assistant_msg)
            for call in tool_calls:
                result = await self._dispatch_tool_call(call, assistant_row.id, session_id, user, db)
                messages.append(
                    {"role": "tool", "name": call["function"]["name"], "content": json.dumps(result.to_dict())}
                )
        else:
            logger.warning("runtime.step_limit_reached", session_id=str(session_id))
            final_content = final_content or "I wasn't able to finish that within the allowed number of steps."

        assistant_final = Message(session_id=session_id, role=MessageRole.ASSISTANT, content=final_content)
        db.add(assistant_final)
        await db.commit()

        # Word-chunked "stream" of the already-complete answer, not genuine
        # token-by-token streaming. Swap in real Ollama streaming for the final
        # answer once the tool loop above is stable - it needs the complete,
        # non-streamed response to reliably parse tool_calls, but nothing stops
        # the *last* iteration (no more tool calls) from streaming for real.
        for word in final_content.split(" "):
            if word:
                yield word + " "
            await asyncio.sleep(0)

    async def _build_context(self, session_id: uuid.UUID, db: AsyncSession) -> list[dict]:
        result = await db.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at.desc())
            .limit(HISTORY_LIMIT)
        )
        history = list(reversed(result.scalars().all()))
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages += [{"role": m.role.value, "content": m.content} for m in history]
        return messages

    async def _dispatch_tool_call(
        self, call: dict, message_id: uuid.UUID, session_id: uuid.UUID, user: UserContext, db: AsyncSession
    ) -> ToolResult:
        name = call["function"]["name"]
        arguments = call["function"].get("arguments") or {}
        if isinstance(arguments, str):
            arguments = json.loads(arguments)

        tool_call_row = ToolCall(message_id=message_id, tool_name=name, arguments=arguments)
        db.add(tool_call_row)
        await db.flush()

        start = time.monotonic()
        tool = registry.get(name)
        if tool is None:
            result = ToolResult(success=False, error=f"Unknown tool: {name}")
        elif tool.is_write:
            # Confirm-before-write gate (section 3): queue it, do not execute.
            result = await self._queue_pending_action(session_id, name, arguments, db)
        else:
            result = await self._execute_with_retry(name, arguments, user)
        duration_ms = int((time.monotonic() - start) * 1000)

        tool_call_row.result = result.to_dict()
        tool_call_row.status = ToolCallStatus.SUCCESS if result.success else ToolCallStatus.FAILURE
        tool_call_row.duration_ms = duration_ms
        await db.commit()

        TOOL_CALL_TOTAL.labels(tool_name=name, status=tool_call_row.status.value).inc()
        logger.info("tool.call", tool_name=name, status=tool_call_row.status.value, duration_ms=duration_ms)
        return result

    async def _queue_pending_action(
        self, session_id: uuid.UUID, tool_name: str, arguments: dict, db: AsyncSession
    ) -> ToolResult:
        pending = PendingAction(session_id=session_id, tool_name=tool_name, arguments=arguments)
        db.add(pending)
        await db.flush()
        return ToolResult(
            success=True,
            data={"pending_action_id": str(pending.id)},
            summary="Queued for human confirmation - it will not execute until approved.",
        )

    async def _execute_with_retry(self, name: str, arguments: dict, user: UserContext) -> ToolResult:
        """Idempotent reads only (section 6) - never call this for write tools."""
        tool = registry.get(name)
        attempts = READ_RETRY_ATTEMPTS if tool and tool.retryable else 1
        result = ToolResult(success=False, error="not_attempted")
        for attempt in range(attempts):
            result = await registry.execute(name, arguments, user)
            if result.success or attempt == attempts - 1:
                return result
            await asyncio.sleep(READ_RETRY_BASE_DELAY_SECONDS * (2**attempt))
        return result
