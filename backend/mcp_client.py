"""The agents' only route to shop facts: the Campus Customs MCP server.

There is deliberately no second tool layer. The backend does not open
``campus_customs_new.db`` anywhere — every stock level, price, lease, invoice, cash
balance, draft and payment goes through the MCP server defined in ``mcp_server/server.py``,
launched from the project's own ``.mcp.json``.

What this module does:

1. Opens one stdio MCP session for a run and keeps it open (``mcp_session``).
2. Turns the tools the server advertises into PydanticAI tools automatically, from the
   server's own JSON schemas — so adding a tool to the MCP server makes it available to
   the agents with no change here.
3. **Withholds ``decide_payment_approval`` from every agent.** That tool is the human's
   approve/reject switch. Keeping it out of the agent toolset is what makes "human
   approval is required for any payment" a property of the system rather than a request
   in a prompt.
4. Logs every tool call — arguments, result, duration, and which agent made it — to
   ``output/audit_trail.json``.
"""

from __future__ import annotations

import json
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from pydantic_ai import RunContext, Tool

import audit
from models import TeamDeps

ROOT = Path(__file__).resolve().parent.parent
MCP_CONFIG = ROOT / ".mcp.json"

#: Tools an agent may never hold. ``decide_payment_approval`` approves money movement;
#: only the human dashboard may call it.
HUMAN_ONLY_TOOLS: frozenset[str] = frozenset({"decide_payment_approval"})

#: Tools that write to the database. Logged with extra prominence on the audit trail.
WRITE_TOOLS: frozenset[str] = frozenset(
    {
        "resolve_ticket",
        "adjust_stock",
        "request_payment_approval",
        "decide_payment_approval",
        "pay",
        "save_draft",
    }
)


def _transport() -> StdioTransport:
    """Build the stdio transport from .mcp.json, so one config drives everything."""
    entry = json.loads(MCP_CONFIG.read_text(encoding="utf-8"))["mcpServers"]["campus-customs"]
    return StdioTransport(
        command=str(ROOT / entry["command"]),
        args=[str(ROOT / a) for a in entry["args"]],
        cwd=str(ROOT),
    )


@asynccontextmanager
async def mcp_session():
    """Open one MCP session for the whole run.

    Agents share it. Spawning a server subprocess per tool call would be both slow and a
    good way to lose the write ordering that the audit trail depends on.
    """
    async with Client(_transport()) as client:
        yield client


async def call_tool(
    client: Any,
    tool: str,
    arguments: dict[str, Any],
    *,
    run_id: str,
    agent: str,
    depth: int = 0,
    ticket_id: int | None = None,
) -> Any:
    """Call one MCP tool and record it on the audit trail, success or failure."""
    started = time.perf_counter()
    try:
        response = await client.call_tool(tool, arguments)
        result = response.data
    except Exception as exc:
        audit.log(
            run_id,
            "tool_call",
            agent,
            depth=depth,
            ticket_id=ticket_id,
            tool=tool,
            arguments=arguments,
            ok=False,
            detail=f"{type(exc).__name__}: {exc}",
            duration_ms=(time.perf_counter() - started) * 1000,
        )
        raise

    audit.log(
        run_id,
        "tool_call",
        agent,
        depth=depth,
        ticket_id=ticket_id,
        tool=tool,
        arguments=arguments,
        result=result,
        ok=True,
        detail="write" if tool in WRITE_TOOLS else "read",
        duration_ms=(time.perf_counter() - started) * 1000,
    )
    return result


async def build_agent_tools(client: Any) -> list[Tool[TeamDeps]]:
    """Turn the MCP server's advertised tools into PydanticAI tools.

    Schemas come from the server itself, so the agents can never drift out of step with
    what the server actually offers. ``HUMAN_ONLY_TOOLS`` are dropped here.
    """
    tools: list[Tool[TeamDeps]] = []

    for spec in await client.list_tools():
        if spec.name in HUMAN_ONLY_TOOLS:
            continue

        def make(tool_name: str):
            async def run_tool(ctx: RunContext[TeamDeps], **kwargs: Any) -> Any:
                return await call_tool(
                    ctx.deps.mcp,
                    tool_name,
                    kwargs,
                    run_id=ctx.deps.run_id,
                    agent=ctx.deps.acting_agent,
                    depth=ctx.deps.depth,
                    ticket_id=ctx.deps.ticket_id,
                )

            return run_tool

        tools.append(
            Tool.from_schema(
                make(spec.name),
                name=spec.name,
                description=spec.description,
                json_schema=getattr(spec, "input_schema", None) or spec.inputSchema,
                takes_ctx=True,
            )
        )

    return tools


async def advertised_tool_names(client: Any) -> list[str]:
    return sorted(t.name for t in await client.list_tools())
