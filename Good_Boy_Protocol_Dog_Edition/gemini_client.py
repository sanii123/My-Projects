"""
gemini_client.py

Gemini does not speak MCP. MCP does not know Gemini exists. This file is
the marriage counselor.

Flow, on every question:
    1. Spin up mcp_server.py as a subprocess, connect over stdio.
    2. Ask it what tools it has (get_full_state, take_luna_for_walk, etc).
    3. Translate those tool schemas into Gemini's FunctionDeclaration format.
    4. Send Gemini the user's question plus the tool list.
    5. Gemini decides which tools to call, in what order, and why.
    6. We actually call them against the live MCP server and feed the
       results back, until Gemini is done investigating and gives a verdict.
    7. Return the verdict AND the full trace of what was checked, in order.

The trace is the entire point of this project. If we only showed the
final sentence, this would just be a chatbot with extra steps.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field

from google import genai
from google.genai import types as gtypes

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

MODEL_NAME = "gemini-2.0-flash"

SYSTEM_INSTRUCTION = """You are the diagnostic layer for a dog named Luna.

You are not allowed to guess. Every claim about why Luna is behaving a
certain way must be backed by at least one tool call. Check the relevant
stats (meal timing, walk timing, energy, boredom, treats today) BEFORE
forming an opinion. If the evidence is ambiguous, say so instead of
picking the more dramatic explanation.

After investigating, give a short, plain-English verdict: what Luna
probably needs, and why, referencing the specific numbers you found.
Do not suggest an action verbally without also being willing to call the
matching action tool if the user asks you to act on it."""


@dataclass
class ToolCallRecord:
    tool_name: str
    arguments: dict
    result: object


@dataclass
class AgentResponse:
    verdict: str
    trace: list[ToolCallRecord] = field(default_factory=list)


def _mcp_tool_to_gemini_declaration(mcp_tool) -> gtypes.FunctionDeclaration:
    """MCP tools describe their inputs as JSON schema. Gemini wants the
    same information under a different name. This is that translation,
    nothing more exciting than that."""
    schema = mcp_tool.inputSchema or {"type": "object", "properties": {}}
    return gtypes.FunctionDeclaration(
        name=mcp_tool.name,
        description=mcp_tool.description or "",
        parameters=schema,
    )


async def ask_about_luna(question: str, api_key: str | None = None) -> AgentResponse:
    """Run one full question through the MCP-tool-calling loop and return
    the verdict plus the reasoning trace."""

    api_key = api_key or os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key)

    server_params = StdioServerParameters(
        command="python",
        args=["mcp_server.py"],
        cwd=os.path.dirname(os.path.abspath(__file__)),
    )

    trace: list[ToolCallRecord] = []

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            mcp_tools = (await session.list_tools()).tools
            declarations = [_mcp_tool_to_gemini_declaration(t) for t in mcp_tools]
            gemini_tools = [gtypes.Tool(function_declarations=declarations)]

            contents: list[gtypes.Content] = [
                gtypes.Content(role="user", parts=[gtypes.Part(text=question)])
            ]

            config = gtypes.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                tools=gemini_tools,
            )

            # Cap the loop so a confused model can't call tools forever.
            for _ in range(8):
                response = client.models.generate_content(
                    model=MODEL_NAME,
                    contents=contents,
                    config=config,
                )

                candidate = response.candidates[0]
                function_calls = [
                    part.function_call
                    for part in candidate.content.parts
                    if part.function_call is not None
                ]

                if not function_calls:
                    # No more tools requested. Whatever text came back is the verdict.
                    verdict = "".join(
                        part.text for part in candidate.content.parts if part.text
                    )
                    return AgentResponse(verdict=verdict.strip(), trace=trace)

                # Gemini wants to call one or more tools. Actually call them.
                contents.append(candidate.content)
                response_parts: list[gtypes.Part] = []

                for call in function_calls:
                    args = dict(call.args or {})
                    result = await session.call_tool(call.name, args)
                    result_value = _extract_tool_result(result)

                    trace.append(
                        ToolCallRecord(tool_name=call.name, arguments=args, result=result_value)
                    )

                    response_parts.append(
                        gtypes.Part(
                            function_response=gtypes.FunctionResponse(
                                name=call.name,
                                response={"result": result_value},
                            )
                        )
                    )

                contents.append(gtypes.Content(role="user", parts=response_parts))

    return AgentResponse(
        verdict="I investigated as much as I'm allowed to in one turn and still couldn't reach a conclusion.",
        trace=trace,
    )


def _extract_tool_result(result) -> object:
    """MCP tool results come back wrapped in content blocks. Most of ours
    are plain JSON-able values, so unwrap down to that."""
    if not result.content:
        return None
    block = result.content[0]
    if hasattr(block, "text"):
        return block.text
    return str(block)


def ask_about_luna_sync(question: str, api_key: str | None = None) -> AgentResponse:
    """Streamlit callbacks are synchronous. This is the bridge."""
    return asyncio.run(ask_about_luna(question, api_key=api_key))


if __name__ == "__main__":
    # Manual smoke test. Requires GOOGLE_API_KEY to be set.
    result = ask_about_luna_sync("Why is Luna staring at me?")
    print("VERDICT:", result.verdict)
    print("TRACE:")
    for step in result.trace:
        print(f"  {step.tool_name}({step.arguments}) -> {step.result}")
