"""FastAPI backend for the Campus Customs dashboard.

The React board talks to this. Every shop fact it serves is read through the MCP server —
there is no SQLite handle anywhere in this file except in `/reset`, which copies the
pristine database file over the working copy and does not read or write rows.

The one route that matters most is **POST /approvals/{id}/decide**. Agents can only queue a
payment with `request_payment_approval`; the human-only `decide_payment_approval` tool is
withheld from all five of them. This route is the human's hand on that switch, and it is the
only path in the system by which cash actually moves.

Runs are started in the background and the board follows them by polling `/events`, because
a three-ticket board takes minutes of model time — far longer than an HTTP request should
hold open.

Start it from the backend directory::

    uvicorn main:app --reload --port 8000
"""

from __future__ import annotations

import asyncio
import shutil
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import agents
import audit
import llm
import mcp_client

ROOT = Path(__file__).resolve().parent.parent
ORIGINAL_DB = ROOT / "data" / "campus_customs.db"
WORKING_DB = ROOT / "data" / "campus_customs_new.db"

#: run_id -> state, so the board can tell a finished run from one still working.
RUNS: dict[str, dict[str, Any]] = {}

#: Only one agent run at a time. Two runs would interleave writes to the same tickets and
#: make the audit trail impossible to read back.
RUN_LOCK = asyncio.Lock()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Fail loudly at startup if the pieces the dashboard depends on are missing."""
    if not WORKING_DB.exists():
        raise RuntimeError(f"Working database missing: {WORKING_DB}. Copy it from {ORIGINAL_DB}.")
    yield


app = FastAPI(
    title="Campus Customs — Multi-Agent Operations",
    description="Backend for the agent dashboard. All shop facts come from the MCP server.",
    version="1.0.0",
    lifespan=lifespan,
)

# The Vite dev server runs on another port, so the board needs CORS to reach this.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:4173", "http://127.0.0.1:4173",
    ],
    allow_methods=["*"],
    allow_credentials=True,
    allow_headers=["*"],
)


# --------------------------------------------------------------------------- schemas


class ApprovalDecision(BaseModel):
    """A human's call on a queued payment."""

    decision: Literal["approve", "reject"]
    decided_by: str = Field(min_length=1, description="Name of the human deciding.")


class RunStarted(BaseModel):
    run_id: str
    ticket_id: int | None
    status: str
    poll: str


# --------------------------------------------------------------------------- helpers


async def _mcp(tool: str, arguments: dict[str, Any] | None = None, *, agent: str = "dashboard") -> Any:
    """Call one MCP tool for a dashboard request, on its own short-lived session."""
    async with mcp_client.mcp_session() as client:
        return await mcp_client.call_tool(
            client, tool, arguments or {}, run_id="dashboard", agent=agent
        )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# =============================================================================
# Tickets
# =============================================================================
@app.get("/tickets", tags=["tickets"])
async def list_tickets() -> dict[str, Any]:
    """Every ticket on the board with its current status, open or resolved.

    Reads through the MCP server: the open board plus each ticket's full record, so the
    dashboard can show resolved tickets too rather than only what is still outstanding.
    """
    async with mcp_client.mcp_session() as client:
        board = await mcp_client.call_tool(
            client, "list_open_tickets", {}, run_id="dashboard", agent="dashboard"
        )
        open_ids = {t["id"] for t in board["tickets"]}
        tickets = list(board["tickets"])

        # The three tickets in this shop are 101-103; fetch any that are no longer open so
        # the board shows the whole set and not just the unfinished part.
        for ticket_id in (101, 102, 103):
            if ticket_id in open_ids:
                continue
            record = await mcp_client.call_tool(
                client, "get_ticket", {"ticket_id": ticket_id},
                run_id="dashboard", agent="dashboard",
            )
            if record.get("found"):
                tickets.append(record["ticket"])

        approvals = await mcp_client.call_tool(
            client, "list_payment_approvals", {"status": "all"},
            run_id="dashboard", agent="dashboard",
        )
        drafts = await mcp_client.call_tool(
            client, "list_drafts", {}, run_id="dashboard", agent="dashboard"
        )

    by_ticket_approvals: dict[int, list[dict]] = {}
    for a in approvals["approvals"]:
        by_ticket_approvals.setdefault(a["ticket_id"], []).append(a)
    by_ticket_drafts: dict[int, list[dict]] = {}
    for d in drafts["drafts"]:
        by_ticket_drafts.setdefault(d["ticket_id"], []).append(d)

    for t in tickets:
        t["approvals"] = by_ticket_approvals.get(t["id"], [])
        t["drafts"] = by_ticket_drafts.get(t["id"], [])

    tickets.sort(key=lambda t: t["id"])
    return {
        "today": board["today"],
        "count": len(tickets),
        "open": sum(1 for t in tickets if t["status"] == "open"),
        "resolved": sum(1 for t in tickets if t["status"] != "open"),
        "tickets": tickets,
    }


@app.get("/tickets/{ticket_id}", tags=["tickets"])
async def get_ticket(ticket_id: int) -> dict[str, Any]:
    """One ticket with its inventory, pricing, lease and invoice rows joined in."""
    record = await _mcp("get_ticket", {"ticket_id": ticket_id})
    if not record.get("found"):
        raise HTTPException(404, record.get("message", f"No ticket {ticket_id}."))
    return record


@app.post("/tickets/{ticket_id}/run", response_model=RunStarted, tags=["agents"])
async def run_ticket(ticket_id: int, background: BackgroundTasks) -> RunStarted:
    """Hand one ticket to the agent team and start working it.

    Returns immediately with a `run_id`; the board follows progress by polling `/events`.
    A ticket run is minutes of model time, so holding the request open would simply time
    out the browser.
    """
    record = await _mcp("get_ticket", {"ticket_id": ticket_id})
    if not record.get("found"):
        raise HTTPException(404, record.get("message", f"No ticket {ticket_id}."))

    if RUN_LOCK.locked():
        raise HTTPException(409, "An agent run is already in progress. Wait for it to finish.")

    run_id = f"run-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:6]}"
    RUNS[run_id] = {
        "run_id": run_id, "ticket_id": ticket_id, "status": "running",
        "started_utc": _now(), "finished_utc": None, "decision": None, "error": None,
    }
    background.add_task(_work_ticket, run_id, ticket_id)

    return RunStarted(
        run_id=run_id, ticket_id=ticket_id, status="running", poll=f"/events?run_id={run_id}"
    )


async def _work_ticket(run_id: str, ticket_id: int) -> None:
    """Background worker: one MCP session, one ticket, fully audited."""
    async with RUN_LOCK:
        try:
            async with mcp_client.mcp_session() as client:
                decision = await agents.run_ticket(client, ticket_id, run_id)
            RUNS[run_id] |= {"status": "finished", "decision": decision.model_dump()}
        except Exception as exc:
            RUNS[run_id] |= {"status": "error", "error": f"{type(exc).__name__}: {exc}"}
            audit.log(run_id, "error", "Boss", ticket_id=ticket_id, ok=False, detail=str(exc))
        finally:
            RUNS[run_id]["finished_utc"] = _now()


@app.get("/runs", tags=["agents"])
async def list_runs() -> dict[str, Any]:
    """Every run this process has started, newest first, with its status."""
    runs = sorted(RUNS.values(), key=lambda r: r["started_utc"], reverse=True)
    return {"count": len(runs), "busy": RUN_LOCK.locked(), "runs": runs}


# =============================================================================
# Agent activity
# =============================================================================
@app.get("/events", tags=["agents"])
async def recent_events(
    limit: int = Query(80, ge=1, le=1000),
    run_id: str | None = None,
    since_seq: int | None = Query(None, description="Only events after this seq in a run."),
) -> dict[str, Any]:
    """Recent agent activity — what each agent did, said, and which tools it used.

    This is the feed the board refreshes on. Every entry carries the agent, the nesting
    depth, the ticket, the tool with its arguments and result, the delegation target, and
    the token cost, straight from `output/audit_trail.json`.
    """
    trail = audit.read_trail()
    events = trail["events"]

    if run_id:
        events = [e for e in events if e.get("run_id") == run_id]
    if since_seq is not None:
        events = [e for e in events if e.get("seq", 0) > since_seq]

    window = events[-limit:]
    return {
        "count": len(window),
        "total_events": len(trail["events"]),
        "latest_seq": window[-1]["seq"] if window else None,
        "busy": RUN_LOCK.locked(),
        "run": RUNS.get(run_id) if run_id else None,
        "events": window,
    }


@app.get("/drafts", tags=["agents"])
async def list_drafts(ticket_id: int | None = None) -> dict[str, Any]:
    """Messages and purchase orders the agents wrote. Nothing here has been sent."""
    args = {} if ticket_id is None else {"ticket_id": ticket_id}
    return await _mcp("list_drafts", args)


# =============================================================================
# Money — the human's side of the gate
# =============================================================================
@app.get("/approvals", tags=["money"])
async def list_approvals(status: str = "all") -> dict[str, Any]:
    """The payment approval queue: what the agents have asked a human to authorise."""
    return await _mcp("list_payment_approvals", {"status": status})


@app.post("/approvals/{approval_id}/decide", tags=["money"])
async def decide_approval(approval_id: int, body: ApprovalDecision) -> dict[str, Any]:
    """Approve or reject a queued payment — and, on approval, actually pay it.

    This is the only route in the system that moves money. The agents prepared the request;
    nothing left the account. Here a named human decides, and on `approve` the payment is
    executed straight away: `payments` gets a row stamped with that human's name,
    `cash_accounts.balance` is debited, and the obligation is updated (an invoice flips to
    `paid`, a lease's next due date rolls forward).

    The payment can still refuse after approval — if the amount exceeds the balance, `pay`
    returns `paid: false` with a reason and the balance is left untouched.
    """
    async with mcp_client.mcp_session() as client:
        decided = await mcp_client.call_tool(
            client, "decide_payment_approval",
            {"approval_id": approval_id, "decision": body.decision,
             "decided_by": body.decided_by},
            run_id="dashboard", agent=f"human:{body.decided_by}",
        )
        if not decided.get("ok"):
            raise HTTPException(400, decided.get("message", "Could not record that decision."))

        if body.decision == "reject":
            balance = await mcp_client.call_tool(
                client, "get_cash_balance", {}, run_id="dashboard", agent="dashboard"
            )
            return {"ok": True, "approval": decided, "payment": None,
                    "balance_after": balance["balance"],
                    "message": f"Approval {approval_id} rejected by {body.decided_by}. "
                               "No money moved."}

        payment = await mcp_client.call_tool(
            client, "pay", {"approval_id": approval_id},
            run_id="dashboard", agent=f"human:{body.decided_by}",
        )
        balance = await mcp_client.call_tool(
            client, "get_cash_balance", {}, run_id="dashboard", agent="dashboard"
        )

    if not payment.get("paid"):
        # Approved, but the pay tool refused — insufficient cash, most likely.
        return {"ok": False, "approval": decided, "payment": payment,
                "balance_after": balance["balance"],
                "message": payment.get("message", "Payment refused.")}

    return {
        "ok": True, "approval": decided, "payment": payment,
        "balance_after": balance["balance"],
        "message": f"Paid ${payment['amount']:,.2f} for {payment['kind']} "
                   f"{payment['ref_id']}, approved by {body.decided_by}. "
                   f"Balance ${payment['balance_before']:,.2f} → ${payment['balance_after']:,.2f}.",
    }


@app.get("/cash", tags=["money"])
async def cash(account: str = "checking") -> dict[str, Any]:
    """The current balance in `cash_accounts`, with what has been paid out of it."""
    async with mcp_client.mcp_session() as client:
        balance = await mcp_client.call_tool(
            client, "get_cash_balance", {"account": account},
            run_id="dashboard", agent="dashboard",
        )
        if not balance.get("found"):
            raise HTTPException(404, balance.get("message", f"No account {account}."))
        approvals = await mcp_client.call_tool(
            client, "list_payment_approvals", {"status": "all"},
            run_id="dashboard", agent="dashboard",
        )

    paid = [a for a in approvals["approvals"] if a["status"] == "paid"]
    pending = [a for a in approvals["approvals"] if a["status"] == "pending"]
    return {
        "account": balance["account"],
        "balance": balance["balance"],
        "as_of": balance["as_of"],
        "today": balance["today"],
        "paid_out_total": round(sum(a["amount"] for a in paid), 2),
        "pending_requests": len(pending),
        "pending_total": round(sum(a["amount"] for a in pending), 2),
        "balance_if_all_pending_approved": round(
            balance["balance"] - sum(a["amount"] for a in pending), 2
        ),
        "note": "Cash only goes out in this shop — no revenue is modelled.",
    }


# =============================================================================
# Reset
# =============================================================================
@app.post("/reset", tags=["admin"])
async def reset_database() -> dict[str, Any]:
    """Restore the working database from the untouched original, for a clean run.

    Copies `data/campus_customs.db` over `data/campus_customs_new.db`. Tickets go back to
    open, cash back to $3,400.00, invoice 501 back to open, and the `approvals` and
    `drafts` tables disappear with the file — the MCP server recreates them empty on its
    next connection.

    The audit trail is deliberately **not** cleared: it is the history of what the agents
    did, and resetting the shop should not erase the record of previous runs.
    """
    if RUN_LOCK.locked():
        raise HTTPException(409, "An agent run is in progress. Wait for it to finish before resetting.")
    if not ORIGINAL_DB.exists():
        raise HTTPException(500, f"Original database missing: {ORIGINAL_DB}")

    shutil.copyfile(ORIGINAL_DB, WORKING_DB)
    RUNS.clear()

    state = await _mcp("list_open_tickets", {}, agent="dashboard")
    balance = await _mcp("get_cash_balance", {}, agent="dashboard")
    audit.log("dashboard", "run_started", "human", detail="database reset to original")

    return {
        "ok": True,
        "reset_from": str(ORIGINAL_DB.relative_to(ROOT)).replace("\\", "/"),
        "reset_to": str(WORKING_DB.relative_to(ROOT)).replace("\\", "/"),
        "open_tickets": [t["id"] for t in state["tickets"]],
        "balance": balance["balance"],
        "today": state["today"],
        "audit_trail": "kept — reset restores the shop, not the record of what agents did",
    }


# =============================================================================
# Health
# =============================================================================
@app.get("/health", tags=["admin"])
async def health() -> dict[str, Any]:
    """Confirm the backend can reach the MCP server, and report what it advertises."""
    async with mcp_client.mcp_session() as client:
        tools = await mcp_client.advertised_tool_names(client)
    return {
        "ok": True,
        "model": llm.MODEL_NAME,
        "mcp_server": "campus-customs",
        "mcp_tools": len(tools),
        "tools_withheld_from_agents": sorted(mcp_client.HUMAN_ONLY_TOOLS),
        "database": "data/campus_customs_new.db",
        "busy": RUN_LOCK.locked(),
    }
