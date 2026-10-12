# Campus Customs — Multi-Agent Operations

**409 AI for Managers · AI Foundation · HW 5 · Yookyung Eom**

A five-agent team runs the back office of Campus Customs, a Yale campus merch shop. Tickets
land on a board; the agents read them, pull in whichever teammates the work needs, and
prepare everything — but **no agent can spend a dollar**. Every payment waits for a human on
a React desk.

Three pieces talk to each other:

- an **MCP server** (FastMCP) — 18 tools, the only route to the shop database
- a **FastAPI backend** — 11 routes and the agent team (PydanticAI, `gpt-6-luna` via Portkey)
- a **React dashboard** (Vite + TypeScript) — watch the agents work and approve payments

---

## Quick start

```bash
# 1. from this folder — create the environment
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt

# 2. add your key
cp .env.example .env     # then paste your PORTKEY_API_KEY into .env

# 3. frontend dependencies
npm install --prefix frontend
```

Then run the three pieces, each in its own terminal — see below.

---

## 1 · Copy the original database to the working copy

`data/campus_customs.db` is the **original** and is never written to. Everything the agents
do lands in `data/campus_customs_new.db`, the **working copy**. Both are committed, so a
clean copy already exists after cloning — but to restore a clean run at any time:

```bash
cp data/campus_customs.db data/campus_customs_new.db
```

On Windows PowerShell:

```powershell
Copy-Item data\campus_customs.db data\campus_customs_new.db -Force
```

The MCP server recreates its two agent-side tables (`approvals`, `drafts`) empty on its next
connection, so this single copy is a complete reset.

## 2 · Start the MCP server

```bash
.venv/Scripts/python.exe mcp_server/server.py
```

It speaks MCP over stdio and is registered in `.mcp.json`, so the backend launches it
automatically — you only need to run it by hand to inspect it directly. To check every tool
against the database:

```bash
.venv/Scripts/python.exe scripts/mcp_smoke_test.py
```

That writes `output/mcp_smoke.json` and exits non-zero if any tool's output disagrees with
`data/campus_customs_new.db`.

## 3 · Start the FastAPI backend

From the `backend/` folder:

```bash
uvicorn main:app --reload --port 8000
```

Live at `http://localhost:8000` (interactive docs at `/docs`). Confirm it can reach the MCP
server:

```bash
curl http://localhost:8000/health
```

## 4 · Start the React board

From the `frontend/` folder:

```bash
npm run dev
```

The desk opens at `http://localhost:5173`. The backend allows that origin via CORS. Pick a
ticket, hand it to the team, watch the wire fill, and approve any payment the agents queue.

## 5 · Reset the database before a full three-ticket run

**Always reset before a full run**, so the board starts from $3,400.00 with all three
tickets open. Either click **“Reset the shop”** on the dashboard, or:

```bash
curl -X POST http://localhost:8000/reset
```

Both restore `data/campus_customs_new.db` from the original. The audit trail is deliberately
**not** cleared — resetting the shop should not erase the record of what the agents did.

Then run the whole board, with the human approvals included, in one command:

```bash
.venv/Scripts/python.exe scripts/full_run.py
```

It resets, works all three tickets through the real HTTP routes, approves each queued
payment as a named human, hands each ticket back so the Boss can close it, and records the
cash position at every step.

---

## What the agents may and may not do

| Rule | How it is enforced |
|---|---|
| **No agent can approve a payment** | `decide_payment_approval` is filtered out of all five agents' toolsets in `backend/mcp_client.py`. It is reachable only from the dashboard. |
| **A payment needs a named human** | `pay()` refuses unless the approval row is `approved`, and writes that person's name into `payments.approved_by`. |
| **Cash cannot go negative** | `pay()` refuses outright rather than clamping. |
| **Stock cannot go negative** | `adjust_stock()` refuses rather than flooring at zero. |
| **Nothing is sent** | There is no send path in the codebase. Messages and purchase orders are saved to `drafts` and stay on the board. |
| **No invented facts** | Every shop number comes from an MCP tool reading a row; a missing row returns `found: false`. The backend never opens the database. |
| **One clock** | Every date comparison uses `desk.date_today` (2026-08-31), never the real date. |

## Model

**`gpt-6-luna` only**, through the Portkey gateway, for every agent. It is named in exactly
one place — `MODEL_NAME` in `backend/llm.py` — and no other model is reachable from the code.
`PORTKEY_API_KEY` is read from `.env` and is never printed, committed, or written to the
audit trail.

---

## File layout

```
hw5/
├── AI_prompts.md              prompt log, one section per problem
├── requirements.txt
├── .env.example               copy to .env and add your key
├── .gitignore
├── .mcp.json                  MCP server registration (stdio)
├── README.md
├── data/
│   ├── campus_customs.db      original — never written to, the reset point
│   └── campus_customs_new.db  working copy — all agent writes land here
├── mcp_server/
│   ├── server.py              18 FastMCP tools
│   └── README.md              purpose, database file, full tool list
├── frontend/                  React + Vite + TypeScript dashboard
├── backend/
│   ├── main.py                11 FastAPI routes
│   ├── models.py              agent output types, run context, audit records
│   ├── agents.py              the five agents and the full delegation mesh
│   ├── llm.py                 the single line that names gpt-6-luna
│   ├── mcp_client.py          MCP session; withholds the human-only tool
│   ├── audit.py               append-only trail writer
│   └── prompts/
│       ├── boss.md
│       ├── inventory.md
│       ├── accounting.md
│       ├── facilities.md
│       └── customer_service.md
├── scripts/
│   ├── mcp_smoke_test.py      tests every MCP tool over a real stdio session
│   ├── full_run.py            drives a whole board run through the HTTP routes
│   └── build_*.py             generate the output files, asserting cash reconciles
└── output/
    ├── harness.md             the full write-up: tables, tools, agents, routes, safety
    ├── mcp_smoke.json         per-tool proof, cross-checked against the database
    ├── desk_tickets.html      Expected vs Actual per ticket, plus Cash and Reflection
    ├── design.md              dashboard design decisions and reasoning
    ├── resolved_tickets.json  per ticket: status, outcome, agent contributions, approvals
    ├── resolved_board.html    the finished board, with a screenshot per ticket
    ├── audit_trail.json       every agent step, appended across runs
    └── github_url.txt         link to this repository
```

## The run that is recorded here

Reset to **$3,400.00**, all three tickets worked, closing balance **$160.00**:

| Ticket | Outcome | Cash |
|---|---|---|
| 101 — Bulldog tee | resolved; blocked behind unpaid invoice 501, which a human then paid | −$840.00 |
| 102 — Rent due | resolved; $2,400.00 rent on lease 1 approved and paid | −$2,400.00 |
| 103 — Bulk hoodie discount | resolved; no discount quoted, because the club named no target price | $0.00 |

`$3,400.00 − $3,240.00 = $160.00`, matching `cash_accounts` exactly. Two payments, both
carrying `approved_by = "Yookyung Eom"`. Five drafts written, **none sent**.

Open `output/desk_tickets.html` and `output/resolved_board.html` in a browser — both are
standalone pages you can double-click.
