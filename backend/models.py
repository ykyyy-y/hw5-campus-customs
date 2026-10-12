"""Data types for the Campus Customs agent team.

Three groups:

* ``AgentName`` and ``AgentOutput`` — what an agent is and what it must hand back.
* ``TeamDeps`` — the run-scoped context every agent shares: the MCP session, the audit
  trail, the run id, and the delegation budget that keeps token use bounded.
* The audit record types that get appended to ``output/audit_trail.json``.

No shop facts live here. Stock, prices, cash, leases and invoices are only ever read
through the MCP server, so there is nothing in this module for a model to copy from.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, Field

# --------------------------------------------------------------------------- agents

AgentName = Literal["Boss", "Inventory", "Accounting", "Facilities", "CustomerService"]

ALL_AGENTS: tuple[AgentName, ...] = (
    "Boss",
    "Inventory",
    "Accounting",
    "Facilities",
    "CustomerService",
)


class AgentOutput(BaseModel):
    """The structured answer every specialist agent returns to whoever asked it.

    Forcing a shape on the reply is what makes delegation cheap: the Boss gets findings
    and a recommendation rather than a paragraph it has to re-read and re-summarise.
    """

    summary: str = Field(
        description="One or two sentences answering exactly what was asked."
    )
    findings: list[str] = Field(
        default_factory=list,
        description="Specific facts pulled from MCP tools, each with its number.",
    )
    recommendation: str = Field(
        default="",
        description="What should happen next, or empty when nothing is recommended.",
    )
    blocked_by: str = Field(
        default="",
        description="What is preventing progress, or empty when nothing is.",
    )
    needs_human_approval: bool = Field(
        default=False,
        description="True when money has to move and a human must sign off first.",
    )


class TicketDecision(BaseModel):
    """The Boss's final call on one ticket, after the specialists have reported."""

    ticket_id: int
    decision: str = Field(description="The call made, in plain language.")
    reasoning: str = Field(description="Why, citing the numbers the tools returned.")
    agents_consulted: list[str] = Field(default_factory=list)
    actions_taken: list[str] = Field(
        default_factory=list,
        description="What was actually written to the database, tool by tool.",
    )
    awaiting_human_approval: list[int] = Field(
        default_factory=list,
        description="Approval ids queued for a human, if any.",
    )
    resolved: bool = Field(
        default=False,
        description="True only when the ticket was actually closed via resolve_ticket.",
    )


# --------------------------------------------------------------------------- run context


@dataclass
class DelegationBudget:
    """Ceilings that stop a fully connected team from talking to itself forever.

    With five agents able to call each other, an unbounded mesh is a token bonfire. Depth
    caps how far a chain can nest; ``max_calls`` caps the whole run; ``spent`` is the
    running count.
    """

    max_depth: int = 2
    max_calls: int = 12
    spent: int = 0

    def can_delegate(self, depth: int) -> tuple[bool, str]:
        if depth >= self.max_depth:
            return False, (
                f"Delegation depth limit reached ({self.max_depth}). "
                "Answer with what you have and with the tools you can call yourself."
            )
        if self.spent >= self.max_calls:
            return False, (
                f"Delegation budget spent ({self.max_calls} calls this run). "
                "Answer with what you have and with the tools you can call yourself."
            )
        return True, ""


@dataclass
class TeamDeps:
    """Everything an agent needs at run time, shared across the whole ticket run.

    ``mcp`` is the one open MCP session. Every shop fact flows through it; no agent holds
    a database handle.
    """

    run_id: str
    mcp: Any
    budget: DelegationBudget = field(default_factory=DelegationBudget)
    depth: int = 0
    ticket_id: int | None = None
    acting_agent: AgentName = "Boss"

    def child(self, agent: AgentName) -> "TeamDeps":
        """A copy of this context one level deeper, for a delegated sub-run."""
        return TeamDeps(
            run_id=self.run_id,
            mcp=self.mcp,
            budget=self.budget,
            depth=self.depth + 1,
            ticket_id=self.ticket_id,
            acting_agent=agent,
        )


# --------------------------------------------------------------------------- audit trail


class AuditEvent(BaseModel):
    """One line of the agent loop, as appended to ``output/audit_trail.json``.

    The fields are chosen so a run can be reconstructed afterwards without the models:
    who acted, at what nesting depth, on which ticket, what they called, with what
    arguments, what came back, how long it took, and what it cost in tokens.
    """

    run_id: str
    seq: int = Field(description="Position within the run, so ordering survives merging.")
    at_utc: str
    event: Literal[
        "run_started",
        "ticket_started",
        "agent_started",
        "tool_call",
        "delegation",
        "delegation_refused",
        "agent_finished",
        "ticket_finished",
        "run_finished",
        "error",
    ]
    agent: str
    depth: int = 0
    ticket_id: int | None = None
    tool: str | None = None
    arguments: dict[str, Any] | None = None
    result: Any = None
    to_agent: str | None = None
    task: str | None = None
    ok: bool = True
    detail: str | None = None
    duration_ms: float | None = None
    model: str | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None


class RunSummary(BaseModel):
    """The tail of a run: what was decided, what moved, and what it cost."""

    run_id: str
    started_utc: str
    finished_utc: str
    shop_date_today: str
    tickets_seen: list[int] = Field(default_factory=list)
    decisions: list[TicketDecision] = Field(default_factory=list)
    approvals_queued: list[int] = Field(default_factory=list)
    total_tool_calls: int = 0
    total_delegations: int = 0
    total_tokens_in: int = 0
    total_tokens_out: int = 0
    model: str = "gpt-6-luna"
