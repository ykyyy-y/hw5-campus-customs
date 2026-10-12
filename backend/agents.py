"""The Campus Customs agent team: Boss, Inventory, Accounting, Facilities, Customer Service.

Five PydanticAI agents, all on **gpt-6-luna** through Portkey, all reaching shop facts
only through the MCP server.

**Full connectivity.** Every agent carries an `ask_teammate` tool listing the other four,
so any agent may delegate to any other — Inventory can hand a frozen vendor to Accounting,
Accounting can ask Customer Service to word a delay, Customer Service can ask the Boss
whether a discount was actually decided. The mesh is complete, not a hub and spoke.

**Bounded.** A complete mesh of five agents will happily talk to itself until the budget is
gone, so delegation is capped by depth and by total calls per run (``DelegationBudget``),
and each agent run is capped by PydanticAI ``UsageLimits``. A refused delegation is not an
error: the agent is told to answer with what it has, and the refusal is logged.

**Audited.** Every agent start, tool call, delegation, refusal and finish is appended to
``output/audit_trail.json`` with its token cost.

Run one ticket, or the whole board::

    .venv/Scripts/python.exe backend/agents.py            # every open ticket
    .venv/Scripts/python.exe backend/agents.py 101        # one ticket
"""

from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic_ai import Agent, RunContext, Tool
from pydantic_ai.exceptions import UsageLimitExceeded

import audit
import llm
import mcp_client
from models import (
    ALL_AGENTS,
    AgentName,
    AgentOutput,
    DelegationBudget,
    RunSummary,
    TeamDeps,
    TicketDecision,
)

PROMPT_DIR = Path(__file__).resolve().parent / "prompts"

#: Role -> prompt file. Five files, five clearly identifiable roles.
PROMPT_FILES: dict[AgentName, str] = {
    "Boss": "boss.md",
    "Inventory": "inventory.md",
    "Accounting": "accounting.md",
    "Facilities": "facilities.md",
    "CustomerService": "customer_service.md",
}

#: One line per agent, injected into every other agent's delegation tool so each knows
#: who to ask for what without being told in prose five times.
ROLE_BLURBS: dict[AgentName, str] = {
    "Boss": "reads tickets, decides who works on them, makes the final call, closes tickets",
    "Inventory": "stock by sku and size, shortfalls, which vendor restocks, lead times and ETAs",
    "Accounting": "cash, invoices, margins, discount floors, queues payments for human approval",
    "Facilities": "leases, rent amounts and due dates, the shop space",
    "CustomerService": "drafts messages to customers, student orgs and the landlord",
}


def load_prompt(agent: AgentName) -> str:
    return (PROMPT_DIR / PROMPT_FILES[agent]).read_text(encoding="utf-8")


def _usage_tokens(result: Any) -> tuple[int, int]:
    """Pull (input, output) tokens off a run result, tolerating shape differences."""
    usage = result.usage() if callable(getattr(result, "usage", None)) else result.usage
    return getattr(usage, "input_tokens", 0) or 0, getattr(usage, "output_tokens", 0) or 0


async def build_team(client: Any) -> dict[AgentName, Agent]:
    """Construct all five agents, wired into a complete delegation mesh.

    The MCP tools are generated from the server's own schemas, so every agent sees the
    same shop surface — minus ``decide_payment_approval``, which is withheld from all of
    them because approving a payment is the human's job.
    """
    mcp_tools = await mcp_client.build_agent_tools(client)
    model = llm.build_model()
    team: dict[AgentName, Agent] = {}

    for name in ALL_AGENTS:
        team[name] = Agent(
            model,
            deps_type=TeamDeps,
            output_type=TicketDecision if name == "Boss" else AgentOutput,
            system_prompt=load_prompt(name),
            # Shop facts via MCP, plus the one tool that reaches the rest of the team.
            tools=[*mcp_tools, _delegation_tool(name, team)],
            name=name,
        )

    return team


def _delegation_tool(from_agent: AgentName, team: dict[AgentName, Agent]) -> Tool[TeamDeps]:
    """Build the `ask_teammate` tool for one agent, closed over who it belongs to.

    ``team`` is captured by reference and is still being populated when this runs; it is
    only read at call time, by which point all five agents exist.
    """
    others = [a for a in ALL_AGENTS if a != from_agent]
    roster = "\n".join(f"- {a}: {ROLE_BLURBS[a]}" for a in others)

    async def ask_teammate(
        ctx: RunContext[TeamDeps], agent_name: str, task: str
    ) -> dict[str, Any]:
        deps = ctx.deps
        target = _resolve_agent_name(agent_name)

        if target is None:
            return {"ok": False,
                    "error": f"No teammate named '{agent_name}'. Available:\n{roster}"}
        if target == from_agent:
            return {"ok": False, "error": "You cannot delegate to yourself."}

        allowed, why = deps.budget.can_delegate(deps.depth)
        if not allowed:
            audit.log(
                deps.run_id, "delegation_refused", from_agent,
                depth=deps.depth, ticket_id=deps.ticket_id,
                to_agent=target, task=task, ok=False, detail=why,
            )
            return {"ok": False, "refused": True, "reason": why}

        deps.budget.spent += 1
        audit.log(
            deps.run_id, "delegation", from_agent,
            depth=deps.depth, ticket_id=deps.ticket_id, to_agent=target, task=task,
            detail=f"delegation {deps.budget.spent}/{deps.budget.max_calls}",
        )

        reply = await run_agent(team[target], target, task, deps.child(target))
        return {"ok": True, "from_agent": target, "reply": reply.model_dump()}

    return Tool(
        ask_teammate,
        name="ask_teammate",
        description=(
            "Delegate a question to another agent on the team and get their findings "
            "back. Name the ticket and include the numbers you already have so they do "
            "not re-fetch what you just read.\n\nTeammates you can ask:\n" + roster
        ),
        takes_ctx=True,
    )


def _resolve_agent_name(raw: str) -> AgentName | None:
    """Accept 'Customer Service', 'customer_service', 'CustomerService', etc."""
    squashed = raw.strip().lower().replace(" ", "").replace("_", "").replace("-", "")
    for candidate in ALL_AGENTS:
        if candidate.lower() == squashed:
            return candidate
    return None


async def run_agent(agent: Agent, name: AgentName, task: str, deps: TeamDeps) -> AgentOutput:
    """Run one specialist agent, audited from start to finish."""
    audit.log(
        deps.run_id, "agent_started", name,
        depth=deps.depth, ticket_id=deps.ticket_id, task=task, model=llm.MODEL_NAME,
    )
    started = time.perf_counter()

    try:
        result = await agent.run(task, deps=deps, usage_limits=llm.SPECIALIST_LIMITS)
    except UsageLimitExceeded as exc:
        audit.log(
            deps.run_id, "error", name,
            depth=deps.depth, ticket_id=deps.ticket_id, ok=False,
            detail=f"usage limit stopped this agent: {exc}",
            duration_ms=(time.perf_counter() - started) * 1000,
        )
        return AgentOutput(
            summary=f"{name} hit its usage limit before finishing.",
            blocked_by=str(exc),
        )

    tokens_in, tokens_out = _usage_tokens(result)
    audit.log(
        deps.run_id, "agent_finished", name,
        depth=deps.depth, ticket_id=deps.ticket_id,
        result=result.output.model_dump(),
        duration_ms=(time.perf_counter() - started) * 1000,
        model=llm.MODEL_NAME, tokens_in=tokens_in, tokens_out=tokens_out,
    )
    return result.output


async def run_ticket(
    client: Any, ticket_id: int, run_id: str, budget: DelegationBudget | None = None
) -> TicketDecision:
    """Put one ticket through the Boss, who pulls in whoever the ticket needs."""
    team = await build_team(client)
    deps = TeamDeps(
        run_id=run_id,
        mcp=client,
        budget=budget or DelegationBudget(),
        ticket_id=ticket_id,
        acting_agent="Boss",
    )

    audit.log(run_id, "ticket_started", "Boss", ticket_id=ticket_id, model=llm.MODEL_NAME)
    started = time.perf_counter()

    task = (
        f"Ticket {ticket_id} is on the board. Read it with get_ticket, work out what it "
        f"actually needs, pull in whichever teammates own the judgment, and make the call. "
        f"Do every action the decision implies — queue approvals, save drafts, adjust stock "
        f"— and only close the ticket if the work is genuinely finished."
    )

    try:
        result = await team["Boss"].run(task, deps=deps, usage_limits=llm.BOSS_LIMITS)
        decision = result.output
        tokens_in, tokens_out = _usage_tokens(result)
    except UsageLimitExceeded as exc:
        audit.log(
            run_id, "error", "Boss", ticket_id=ticket_id, ok=False,
            detail=f"usage limit stopped this ticket: {exc}",
            duration_ms=(time.perf_counter() - started) * 1000,
        )
        return TicketDecision(
            ticket_id=ticket_id,
            decision="Stopped early.",
            reasoning=f"The Boss hit its usage limit: {exc}",
        )

    audit.log(
        run_id, "ticket_finished", "Boss", ticket_id=ticket_id,
        result=decision.model_dump(),
        duration_ms=(time.perf_counter() - started) * 1000,
        model=llm.MODEL_NAME, tokens_in=tokens_in, tokens_out=tokens_out,
    )
    return decision


async def run_board(ticket_ids: list[int] | None = None) -> RunSummary:
    """Work the whole board (or the tickets given), one MCP session for the lot."""
    run_id = f"run-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:6]}"
    started_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")

    async with mcp_client.mcp_session() as client:
        board = await mcp_client.call_tool(
            client, "list_open_tickets", {}, run_id=run_id, agent="Boss"
        )
        today = board["today"]
        ids = ticket_ids or [t["id"] for t in board["tickets"]]

        audit.log(
            run_id, "run_started", "Boss",
            detail=f"{len(ids)} ticket(s) to work: {ids}; shop today {today}",
            model=llm.MODEL_NAME,
        )

        decisions: list[TicketDecision] = []
        budget = DelegationBudget()
        for ticket_id in ids:
            decisions.append(await run_ticket(client, ticket_id, run_id, budget))

        approvals = await mcp_client.call_tool(
            client, "list_payment_approvals", {"status": "all"},
            run_id=run_id, agent="Boss",
        )

    events = audit.events_for_run(run_id)
    summary = RunSummary(
        run_id=run_id,
        started_utc=started_utc,
        finished_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        shop_date_today=today,
        tickets_seen=ids,
        decisions=decisions,
        approvals_queued=[a["id"] for a in approvals["approvals"]],
        total_tool_calls=sum(1 for e in events if e["event"] == "tool_call"),
        total_delegations=sum(1 for e in events if e["event"] == "delegation"),
        total_tokens_in=sum(e.get("tokens_in") or 0 for e in events),
        total_tokens_out=sum(e.get("tokens_out") or 0 for e in events),
        model=llm.MODEL_NAME,
    )
    audit.log(
        run_id, "run_finished", "Boss",
        detail=f"{len(decisions)} ticket(s) decided",
        model=llm.MODEL_NAME,
        tokens_in=summary.total_tokens_in, tokens_out=summary.total_tokens_out,
    )
    audit.log_run_summary(summary)
    return summary


async def _main(argv: list[str]) -> int:
    ids = [int(a) for a in argv] or None
    summary = await run_board(ids)

    print(f"\nrun {summary.run_id}  (model: {summary.model}, shop today {summary.shop_date_today})")
    for d in summary.decisions:
        print(f"\n  ticket {d.ticket_id}  resolved={d.resolved}")
        print(f"    decision : {d.decision}")
        print(f"    consulted: {', '.join(d.agents_consulted) or '-'}")
        for action in d.actions_taken:
            print(f"    action   : {action}")
        if d.awaiting_human_approval:
            print(f"    awaiting human approval: {d.awaiting_human_approval}")
    print(
        f"\n  tool calls {summary.total_tool_calls} | delegations {summary.total_delegations}"
        f" | tokens in {summary.total_tokens_in} out {summary.total_tokens_out}"
    )
    print("  audit trail appended to output/audit_trail.json")
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(asyncio.run(_main(sys.argv[1:])))
