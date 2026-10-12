# Campus Customs MCP Server

## 1. What this server is for

This is the single door between the Campus Customs agent team and the shop's records.
Every agent — Boss, Inventory, Accounting, Facilities, Customer Service — reads and writes
the shop's state through the tools exposed here, rather than opening the database on its
own. The backend in `backend/` contains **no second tool layer and no database handle**:
if a number reaches an agent, it came through this server. Built with **FastMCP**.

Four rules define the server:

- **No invented data.** Every value a tool returns was read out of the database. A missing
  row returns `found: false` with a plain message instead of a plausible guess.
- **One shop clock.** "Today" is `desk.date_today` (currently **2026-08-31**), never the real
  wall clock, so overdue and due-soon judgments match the shop's own calendar.
- **Money rules live in code, not in prompts.** `pay` refuses unless a named human approved
  that exact payment, and refuses again if it would drive the cash balance below zero.
  `adjust_stock` refuses to take stock negative.
- **Nothing is sent.** There is no send path in this codebase. Customer messages, landlord
  replies and purchase orders are saved as drafts and stay on the board.

## 2. Database file

`data/campus_customs_new.db` — the working copy, resolved relative to this file as
`../data/campus_customs_new.db`.

The pristine original `data/campus_customs.db` is never opened by this server, so a run can
always be reset by re-copying it over the working file.

Two tables are created in the working copy on first use, because the shop's original schema
has nowhere to put them:

- **`approvals`** — the human approval queue that gates every payment
- **`drafts`** — messages and purchase orders that are written but never sent

## 3. Tools in this server

18 tools. R = reads, **W** = writes.

### The ticket board

| Tool | Tables |
|---|---|
| `list_open_tickets()` | R `tickets`, `desk` |
| `get_ticket(ticket_id)` | R `tickets` + joins into `inventory`, `pricing`, `leases`, `invoices` |
| `resolve_ticket(ticket_id, resolution, resolved_by)` | **W** `tickets` |

### Inventory and pricing

| Tool | Tables |
|---|---|
| `check_stock(sku, size, qty_wanted=1)` | R `inventory`, `desk` |
| `adjust_stock(sku, size, delta, reason, changed_by)` | **W** `inventory` — refuses to go negative |
| `price_quote(sku, qty, proposed_unit_price=None)` | R `pricing`, `desk` |

### Vendors

| Tool | Tables |
|---|---|
| `list_vendors()` | R `vendors` |
| `get_vendor_status(vendor_id)` | R `vendors`, `invoices`, `desk` — `can_ship: false` when an invoice is open |
| `estimate_restock_eta(vendor_id, from_date=None)` | R `vendors`, `desk` |

### Facilities

| Tool | Tables |
|---|---|
| `get_rent_due(lease_id)` | R `leases`, `desk` |

### Money

| Tool | Tables |
|---|---|
| `get_cash_balance(account="checking")` | R `cash_accounts`, `desk` |
| `list_invoices(status="open")` | R `invoices`, `vendors`, `desk` |
| `request_payment_approval(kind, ref_id, amount, reason, requested_by, ticket_id=None)` | **W** `approvals`, R `cash_accounts` — **moves no money** |
| `list_payment_approvals(status="all")` | R `approvals` |
| `decide_payment_approval(approval_id, decision, decided_by)` ⚠ | **W** `approvals` — **HUMAN ONLY** |
| `pay(approval_id)` | **W** `payments`, `cash_accounts`, `invoices`/`leases`, `approvals` |

### Drafts — nothing is ever sent

| Tool | Tables |
|---|---|
| `save_draft(ticket_id, kind, audience, subject, body, created_by)` | **W** `drafts` |
| `list_drafts(ticket_id=None)` | R `drafts` |

### ⚠ The one tool agents cannot have

`decide_payment_approval` is the human's approve/reject switch. It is listed in
`HUMAN_ONLY_TOOLS` in `backend/mcp_client.py` and filtered out before the toolset is handed
to any agent, so no agent can approve its own payment request. Agents reach money only
through `request_payment_approval`, which queues a request and moves nothing.

### The first three tools, and the tickets they unlock

`check_stock`, `get_rent_due` and `price_quote` were built first, one per open ticket:

- **`check_stock` → ticket 101.** Stock is keyed by `(sku, size)`, so only a size-aware
  lookup can prove the order cannot be filled: it returns `on_hand: 0, shortfall: 1` for
  `CC-TEE-WHITE` / `S`, the number Inventory needs before routing a reprint to a vendor.
- **`get_rent_due` → ticket 102.** The ticket carries a `lease_id` and a landlord's email
  claim but no amount, so this resolves lease 1 to $2,400.00 due 2026-09-02 with
  `days_until_due: 2` from the shop's own clock.
- **`price_quote` → ticket 103.** A discount ask with no number attached, so it prices the
  exact 20 units at $1,160 list on $440 cost (62.1% margin) and names $22.00/unit as the
  floor straight from `pricing.unit_cost`.

## Running it

```bash
.venv/Scripts/python.exe mcp_server/server.py
```

Registered for clients in `.mcp.json` at the project root. `scripts/mcp_smoke_test.py`
launches it from that same config and checks each tool's output against the database.
