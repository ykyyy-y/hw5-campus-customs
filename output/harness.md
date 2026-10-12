# Campus Customs — Agent Harness

**Assignment:** HW 5 — Campus Customs Multi-Agent Operations
**Author:** Yookyung Eom
**Database (original, never written to):** `data/campus_customs.db`
**Database (working copy, all agent writes land here):** `data/campus_customs_new.db`
**Shop "today" (`desk.date_today`):** **2026-08-31**

This harness is the shared reference the agent team works from. It starts with the database
map and grows in later problems to cover the MCP tools, the agents, the safety rules, and
the run specs.

---

## 1. Database map

Nine tables, all present in the working copy. For each: its fields, and one line on why that
field matters to the agents.

### 1.1 `desk` — the shop clock

| Field | Type | Why it matters to the agents |
|---|---|---|
| `date_today` | TEXT | The shop's "today" (**2026-08-31**); every overdue / due-soon judgment is measured against this, never against the real wall clock. |
| `notes` | TEXT | Free-text desk memo; carries any standing instruction to the Boss that is not encoded in a ticket. |

**Current value:** `date_today = 2026-08-31`, `notes = NULL`.

### 1.2 `tickets` — the work board

| Field | Type | Why it matters to the agents |
|---|---|---|
| `id` | INTEGER PK | The unit of work; every agent action is traceable back to a ticket id. |
| `type` | TEXT | The routing key the Boss reads first — `customer_order`, `rent_notice`, `price_override` each imply a different lead agent. |
| `requester` | TEXT | Who is waiting; decides whether Customer Service drafts to a customer, a student org, or a landlord. |
| `subject` | TEXT | One-line summary the Boss triages on before pulling the full record. |
| `sku` | TEXT | Joins to `inventory.sku` and `pricing.sku`; null when the ticket is not about a product. |
| `size` | TEXT | Second half of the inventory key — stock is per `(sku, size)`, so size alone decides whether a shortfall exists. |
| `qty` | INTEGER | Units requested; compared against `inventory.qty` to size the shortfall and the restock. |
| `lease_id` | INTEGER FK to `leases.id` | Points a facilities ticket at the exact lease, so rent amount and due date are read, not guessed. |
| `invoice_id` | INTEGER FK to `invoices.id` | Links the ticket to a vendor bill — the signal that the ticket is blocked behind an unpaid invoice. |
| `status` | TEXT | `open` vs resolved; defines the queue the agents must clear and what a "full run" means. |
| `notes` | TEXT | The human context (what the requester actually asked for) that the model needs to draft a sensible reply. |
| `created_at` | TEXT | Arrival order; the tiebreaker when two tickets compete for the same limited cash. |

### 1.3 `inventory` — stock truth

| Field | Type | Why it matters to the agents |
|---|---|---|
| `sku` | TEXT, PK part 1 | Product identifier shared with `pricing` and with ticket lines. |
| `name` | TEXT | Human-readable product name for customer drafts and purchase orders. |
| `size` | TEXT, PK part 2 | Stock is tracked per size, so `(sku, size)` is the real key — "we have hoodies" is never a valid answer. |
| `qty` | INTEGER | Units on hand; `qty - ticket.qty < 0` is the definition of a shortfall, and this is the field a fulfilled order decrements. |
| `location` | TEXT | Aisle for picking; goes into the fulfillment note so a human can actually find the item. |

**Current stock (10 rows):**

| SKU | Name | S | M | L | XL | OS | Location |
|---|---|---|---|---|---|---|---|
| `CC-HOOD-NAVY` | Basic Hoodie Big Yale | 4 | 8 | 14 | 6 | — | Aisle A |
| `CC-TEE-WHITE` | Classic Bulldog Tee | **0** | 5 | 3 | 2 | — | Aisle B |
| `CC-HAT-BLUE` | Yale Cap | — | — | — | — | 40 | Aisle C |
| `CC-MUG-CREST` | Crest Mug | — | — | — | — | **0** | Aisle D |

### 1.4 `pricing` — cost and margin

| Field | Type | Why it matters to the agents |
|---|---|---|
| `sku` | TEXT PK | Joins pricing to the inventory line and to any ticket naming that SKU. |
| `unit_cost` | REAL | What the shop pays; the hard floor Accounting defends when a discount is requested. |
| `list_price` | REAL | Sticker price; the baseline a discount is measured down from and the revenue input to any margin check. |

**Current pricing and discount headroom:**

| SKU | Unit cost | List price | Gross margin | Max discount before hitting cost |
|---|---|---|---|---|
| `CC-HOOD-NAVY` | $22.00 | $58.00 | 62.1% | 62.1% |
| `CC-TEE-WHITE` | $8.00 | $28.00 | 71.4% | 71.4% |
| `CC-HAT-BLUE` | $6.00 | $22.00 | 72.7% | 72.7% |
| `CC-MUG-CREST` | $3.50 | $14.00 | 75.0% | 75.0% |

### 1.5 `vendors` — who can restock

| Field | Type | Why it matters to the agents |
|---|---|---|
| `id` | INTEGER PK | Joins to `invoices.vendor_id` — the key that reveals whether a vendor is blocked by an unpaid bill. |
| `name` | TEXT | Named on the purchase order and in the customer's ETA message. |
| `specialty` | TEXT | Matches a shortfall to the right vendor — apparel goes to the apparel printer, mugs to the gift supplier. |
| `lead_days` | INTEGER | The only legitimate source of an ETA; agents must read it here rather than inventing a delivery date. |

| id | Name | Specialty | Lead days |
|---|---|---|---|
| 1 | Bulldog Print Co | apparel reprint | 5 |
| 2 | Elm City Gifts | mugs and small goods | 3 |
| 3 | QuickShip CT | local courier | 1 |

### 1.6 `invoices` — what the shop owes

| Field | Type | Why it matters to the agents |
|---|---|---|
| `id` | INTEGER PK | Referenced by `tickets.invoice_id`, and recorded as `payments.ref_id` once paid. |
| `vendor_id` | INTEGER FK to `vendors.id` | Identifies which vendor is frozen — an open invoice blocks new shipments from that vendor. |
| `amount` | REAL | The exact payment amount, checked against the cash balance before approval is requested. |
| `due_date` | TEXT | Compared to `desk.date_today` to flag overdue; drives payment priority. |
| `status` | TEXT | `open` vs `paid` — the gate on vendor shipping, and the field that must be updated after a payment clears. |
| `description` | TEXT | Explains what the bill is for, so the Boss can tie it to the right ticket. |

**Current:** invoice **501**, vendor 1 (Bulldog Print Co), **$840.00**, due **2026-08-28**,
status **open** — **3 days overdue** as of 2026-08-31.

### 1.7 `leases` — the shop space

| Field | Type | Why it matters to the agents |
|---|---|---|
| `id` | INTEGER PK | Target of `tickets.lease_id` for rent and facilities tickets. |
| `space_name` | TEXT | Which space the notice is about, when the shop holds more than one. |
| `landlord` | TEXT | The counterparty Customer Service addresses in a rent reply draft. |
| `monthly_rent` | REAL | The authoritative rent amount — paid from here, never from a number quoted in an email. |
| `next_due` | TEXT | Compared to `desk.date_today` to decide "due soon" vs "overdue" and to rank against other cash claims. |
| `notes` | TEXT | Lease conditions that could change the recommendation. |

**Current:** lease 1, Chapel Street shop, Elm City Properties, **$2,400.00/month**, next due
**2026-09-02** — **due in 2 days**.

### 1.8 `cash_accounts` — the spending limit

| Field | Type | Why it matters to the agents |
|---|---|---|
| `name` | TEXT PK | The account a payment is drawn from, written into `payments.account`. |
| `balance` | REAL | The hard constraint — the pay tool must refuse any payment that would push this below zero, and money only ever leaves. |
| `date` | TEXT | As-of date of the balance, so agents know the figure is current to the shop's today. |

**Current:** `checking` = **$3,400.00** as of 2026-08-31.

### 1.9 `payments` — the approval audit trail

| Field | Type | Why it matters to the agents |
|---|---|---|
| `id` | INTEGER PK | One row per payment actually made; the ledger a grader can audit. |
| `kind` | TEXT | What was paid — `invoice` or `rent` — so cash out can be attributed. |
| `ref_id` | INTEGER | The invoice id or lease id paid, linking the payment back to its obligation. |
| `amount` | REAL | Amount debited; must reconcile with the drop in `cash_accounts.balance`. |
| `account` | TEXT | Which account was drawn down. |
| `paid_at` | TEXT | Payment date, stamped from `desk.date_today`, not the real clock. |
| `approved_by` | TEXT | **The human approval record** — a payment row without a real approver means the approval rule was broken. |

**Current:** empty (0 rows) — nothing has been paid yet.

---

## 2. The three open tickets and how they connect

All three tickets are `status = 'open'` and all arrived on 2026-08-31, the shop's today.

### Ticket 101 — `customer_order` — Tauhid Zaman — "Bulldog tee"

`sku = CC-TEE-WHITE`, `size = S`, `qty = 1`, `invoice_id = 501`

**Join chain:** `tickets.sku + size` → `inventory(CC-TEE-WHITE, S).qty = 0` → **short 1 unit**.
`tickets.sku` → `pricing(CC-TEE-WHITE)` = $8.00 cost / $28.00 list.
The shortfall is apparel → `vendors.specialty = 'apparel reprint'` → **vendor 1, Bulldog
Print Co, 5 lead days**. And `tickets.invoice_id = 501` → `invoices(501)` is **open, $840,
3 days overdue**, owed to **that same vendor 1**.

**Why it is blocked:** a vendor will not ship while it has an open unpaid invoice, so the tee
cannot be reprinted until invoice 501 is paid — which needs cash, which needs human approval.
The earliest honest ETA for the customer is **payment date + 5 days**, not 5 days from today.

### Ticket 102 — `rent_notice` — Elm City Properties — "Rent due"

`lease_id = 1`, no SKU

**Join chain:** `tickets.lease_id` → `leases(1)` = Chapel Street shop, **$2,400.00**, next due
**2026-09-02** → **2 days out** from `desk.date_today`. Paying would debit
`cash_accounts.checking` and write a `payments` row with `kind = 'rent'`, `ref_id = 1`.

**Why it matters:** it is the largest single claim on cash, and it competes directly with
ticket 101's vendor invoice.

### Ticket 103 — `price_override` — Yale AI Club — "Bulk hoodie discount"

`sku = CC-HOOD-NAVY`, `size = M`, `qty = 20`

**Join chain:** `inventory(CC-HOOD-NAVY, M).qty = 8` → **short 12 units**.
`pricing(CC-HOOD-NAVY)` = $22.00 cost / $58.00 list → a full-price order is $1,160 revenue on
$440 of cost, a **62.1% margin**, so there is real discount headroom but the agreed price
must stay above $22.00/unit. Restocking the missing 12 hoodies is apparel → **vendor 1 again,
5 lead days**.

**Why it is blocked too:** the 12-unit shortfall routes to the same Bulldog Print Co that is
sitting on open invoice 501.

### The shared dependency

```
            invoice 501 (OPEN, $840, 3 days overdue)
                        |  owed to
                        v
            vendor 1 - Bulldog Print Co (apparel, 5-day lead)
                   ^                    ^
      needs reprint |                    | needs 12 more hoodies
                    |                    |
        Ticket 101 (tee S, short 1)   Ticket 103 (hoodie M, short 12)

        Ticket 102 (rent $2,400 due 2026-09-02) -- competes for the same cash
```

**Cash arithmetic.** Checking holds **$3,400.00**. Invoice 501 ($840) + rent ($2,400) =
**$3,240**, leaving **$160**. Both are affordable, in either order, but nothing else is — and
since no revenue is modelled, that $160 is the shop's entire remaining runway. Any third
spend (for example, prepaying a purchase order for the 12 hoodies) must be refused by the pay
tool rather than driving the balance negative.

**What this implies for the agent team.** Ticket 101 is not really a Customer Service problem;
it is an Accounting problem wearing a customer's clothes. Ticket 103 looks like a pricing
question but is half an inventory and vendor question. This is exactly why the team needs full
connectivity — Inventory has to hand the shortfall to Accounting, and Accounting has to hand
the payment-dependent ETA back to Customer Service before any message goes out.

---

## 3. Models and agents

### 3.1 Model

| | |
|---|---|
| **Model** | **`gpt-6-luna`** — the only model any agent uses |
| **Gateway** | Portkey, `https://api.portkey.ai/v1` |
| **Credential** | `PORTKEY_API_KEY`, read from the repository root `.env`; never printed, logged, or written to the audit trail |
| **API** | OpenAI **Responses** API (`OpenAIResponsesModel`) |
| **Where it is set** | `backend/llm.py`, in the single constant `MODEL_NAME = "gpt-6-luna"` |

All five agents are built from one `build_model()` call, so exactly one line in the project
names a model and no other model is reachable from the code.

The Responses API is used deliberately: function tools fail on Portkey's chat/completions
path for this model, and every agent here is tool-driven.

### 3.2 The five agents

Framework: **PydanticAI**. One prompt file per agent in `backend/prompts/`, the agents
themselves in `backend/agents.py`, the shared data types in `backend/models.py`.

| Agent | Prompt file | Owns | Returns |
|---|---|---|---|
| **Boss** | `prompts/boss.md` | Reads each ticket, decides who works it, makes the final call, and is the only agent that closes a ticket | `TicketDecision` |
| **Inventory** | `prompts/inventory.md` | Stock by `(sku, size)`, shortfalls, vendor matching, lead times and ETAs | `AgentOutput` |
| **Accounting** | `prompts/accounting.md` | Cash, invoices, margins, discount floors; queues payments for human approval | `AgentOutput` |
| **Facilities** | `prompts/facilities.md` | Leases, rent amounts and due dates, the shop space | `AgentOutput` |
| **Customer Service** | `prompts/customer_service.md` | Drafts messages to customers, student orgs and the landlord | `AgentOutput` |

Structured output is doing real work here: a specialist hands back `summary`, `findings`,
`recommendation`, `blocked_by` and `needs_human_approval` rather than a paragraph, so the
Boss receives facts it can act on instead of prose it has to re-read and re-summarise.

### 3.3 Full connectivity

Every agent carries an **`ask_teammate(agent_name, task)`** tool listing the other four, so
**any agent may delegate to any other** — this is a complete mesh, not a hub and spoke. The
tool's description embeds the roster with each teammate's remit, so an agent knows who to
ask without that being repeated in five prompts.

Observed in the live run (`output/audit_trail.json`): Customer Service delegated to
Facilities, which delegated onward to Accounting — a chain that never passes through the
Boss, which is exactly what full connectivity is for.

### 3.4 The agent loop

```
run_board()
  └─ list_open_tickets                      (MCP)
      └─ for each ticket: run_ticket()
           └─ Boss.run(...)                 depth 0
                ├─ get_ticket               (MCP, joins inventory/pricing/lease/invoice)
                ├─ ask_teammate(...)  ──────▶ Specialist.run(...)        depth 1
                │                                ├─ MCP tools
                │                                └─ ask_teammate(...) ──▶ Specialist  depth 2
                │                                                            └─ depth limit:
                │                                                               refused + logged
                ├─ actions: request_payment_approval / save_draft / adjust_stock
                └─ resolve_ticket            (only if the work actually finished)
```

Each step — agent start, every tool call with its arguments and result, every delegation,
every refusal, every finish with its token cost — is appended to `output/audit_trail.json`.

## 4. MCP tools

Built with **FastMCP**, in `mcp_server/server.py`. All tools open
`data/campus_customs_new.db` only; the original `data/campus_customs.db` is never touched, so
a run can always be reset. **No tool invents a value** — every number returned was read from a
row, and a missing row comes back as `found: False` with a message rather than a guess. "Today"
always comes from `desk.date_today` (2026-08-31), never the real clock.

**18 tools.** The three below were built first, one per open ticket; the other fifteen were
added so the team can actually work a ticket end to end. Section 4.6 is the complete list
with the table each one touches.

The backend holds **no second tool layer** — `backend/` never opens the database. Every
shop fact the agents see arrives through this server.

### 4.1 `check_stock(sku, size, qty_wanted=1)` → **Ticket 101**

| | |
|---|---|
| **Reads** | `inventory` (keyed on `sku` + `size`); `desk.date_today` for the as-of stamp |
| **Returns** | `name`, `on_hand`, `location`, `qty_wanted`, `can_fill`, `shortfall`, `as_of` |
| **Unlocks** | **Ticket 101** — Tauhid Zaman's order for `CC-TEE-WHITE`, size `S`, qty 1 |

**Why this tool fits ticket 101:** ticket 101 names a SKU *and* a size, and stock is stored per
`(sku, size)`, so only a size-aware lookup can prove the order cannot be filled — this tool
returns `on_hand: 0, can_fill: false, shortfall: 1` for that exact pair, which is the number
Inventory needs before it can route a reprint to a vendor.

Live result against the working copy:

```json
{"found": true, "sku": "CC-TEE-WHITE", "name": "Classic Bulldog Tee", "size": "S",
 "on_hand": 0, "location": "Aisle B", "qty_wanted": 1, "can_fill": false,
 "shortfall": 1, "as_of": "2026-08-31"}
```

### 4.2 `get_rent_due(lease_id)` → **Ticket 102**

| | |
|---|---|
| **Reads** | `leases` (amount, due date, landlord); `desk.date_today` to date the comparison |
| **Returns** | `space_name`, `landlord`, `monthly_rent`, `next_due`, `days_until_due`, `is_overdue` |
| **Unlocks** | **Ticket 102** — Elm City Properties' rent notice, carrying `lease_id = 1` |

**Why this tool fits ticket 102:** ticket 102 carries a `lease_id` and an email claim ("rent due
in 2 days") but no amount, so the agents must get both the figure and the date from the lease of
record — this tool resolves lease 1 to $2,400.00 due 2026-09-02 and computes
`days_until_due: 2` against the shop's own clock, which is what lets Accounting size the
payment request without trusting the landlord's wording.

Live result against the working copy:

```json
{"found": true, "lease_id": 1, "space_name": "Chapel Street shop",
 "landlord": "Elm City Properties", "monthly_rent": 2400.0, "next_due": "2026-09-02",
 "today": "2026-08-31", "days_until_due": 2, "is_overdue": false}
```

### 4.3 `price_quote(sku, qty, proposed_unit_price=None)` → **Ticket 103**

| | |
|---|---|
| **Reads** | `pricing` (`unit_cost`, `list_price`); `desk.date_today` for the as-of stamp |
| **Returns** | `total_cost`, `list_revenue`, `list_margin_pct`, `cost_floor_unit_price`, `max_discount_pct_before_cost`, and — when a price is proposed — `proposed_discount_pct`, `proposed_margin`, `above_cost` |
| **Unlocks** | **Ticket 103** — the Yale AI Club's bulk-discount ask on 20 `CC-HOOD-NAVY`, size `M` |

**Why this tool fits ticket 103:** ticket 103 is a discount request with no number attached, so
the decision hinges entirely on how far the hoodie's price can fall before it hits cost — this
tool prices the club's exact 20 units at $1,160 list on $440 cost (62.1% margin), names
$22.00/unit as the floor straight from `pricing.unit_cost`, and scores any proposed price
against it, so the Boss approves or refuses a discount on arithmetic instead of goodwill.

Live result against the working copy, testing a 20% discount:

```json
{"found": true, "sku": "CC-HOOD-NAVY", "qty": 20, "unit_cost": 22.0, "list_price": 58.0,
 "total_cost": 440.0, "list_revenue": 1160.0, "list_margin": 720.0, "list_margin_pct": 62.1,
 "cost_floor_unit_price": 22.0, "max_discount_pct_before_cost": 62.1,
 "proposed_unit_price": 46.4, "proposed_discount_pct": 20.0, "proposed_revenue": 928.0,
 "proposed_margin": 488.0, "proposed_margin_pct": 52.6, "above_cost": true}
```

### 4.4 Connection config and smoke test

The server is registered in **`.mcp.json`** at the project root, launched over **stdio**:

```json
{
  "mcpServers": {
    "campus-customs": {
      "command": ".venv/Scripts/python.exe",
      "args": ["mcp_server/server.py"],
      "env": {}
    }
  }
}
```

`scripts/mcp_smoke_test.py` reads that same `.mcp.json`, launches the server as a subprocess,
completes the MCP handshake, lists the tools the server advertises, and calls each one — the
tool functions are never imported directly, so the test exercises the real protocol path. Each
result is then cross-checked against a direct SQL read of the working copy.

Proof is written to **`output/mcp_smoke.json`**, which records, per tool: the prompt asked, the
tool name, the arguments, the full tool output, the verification SQL, the matching database row,
and a `matches_database` flag.

| Ticket | Tool | Key output | Matches DB |
|---|---|---|---|
| 101 | `check_stock` | `on_hand: 0`, `can_fill: false`, `shortfall: 1`, Aisle B | yes |
| 102 | `get_rent_due` | `$2,400.00`, due `2026-09-02`, `days_until_due: 2` | yes |
| 103 | `price_quote` | list `$1,160` on `$440` cost, 62.1%, floor `$22.00`, `above_cost: true` at `$46.40` | yes |

Run summary: `tools_advertised_by_server == tools_tested` (all three),
`all_outputs_match_database: true`. The smoke test only reads, so the working copy is
byte-identical to the original afterward.

### 4.5 Tools added so the team can work a ticket end to end

The first three tools answer questions. These fifteen let the team act — and two of them,
`request_payment_approval` and `pay`, are where the shop's money rules are enforced in code.

**The ticket board**

- **`list_open_tickets()`** — `tickets` (+ `desk`). The Boss's entry point: a run discovers
  what work exists instead of being handed a list.
- **`get_ticket(ticket_id)`** — `tickets`, following its foreign keys into `inventory`,
  `pricing`, `leases` and `invoices`. One call returns the whole dependency, which is how
  the Boss sees that ticket 101 is really an invoice problem.
- **`resolve_ticket(ticket_id, resolution, resolved_by)`** — writes `tickets.status` and
  appends to `tickets.notes`. Refuses a ticket that is already closed.

**Inventory**

- **`adjust_stock(sku, size, delta, reason, changed_by)`** — writes `inventory.qty`.
  **Refuses rather than clamps** when a change would go below zero, so the books never claim
  stock that never existed.

**Vendors**

- **`list_vendors()`** — `vendors`. Specialty is how a shortfall is matched to a supplier.
- **`get_vendor_status(vendor_id)`** — `vendors` + `invoices` + `desk`. Returns `can_ship`,
  the blocking invoices with days overdue, and a dated ETA. A vendor holding any open invoice
  comes back `can_ship: false` with a `blocking_reason`, which is the shop's no-ship rule made
  mechanical.
- **`estimate_restock_eta(vendor_id, from_date=None)`** — `vendors.lead_days` + `desk`. Pass
  the expected payment date as `from_date` so a blocked restock is quoted as *payment date +
  lead days*, not *today + lead days*.

**Money**

- **`get_cash_balance(account)`** — `cash_accounts`. The hard ceiling on everything.
- **`list_invoices(status)`** — `invoices` joined to `vendors`, with days overdue against
  `desk.date_today`.
- **`request_payment_approval(kind, ref_id, amount, reason, requested_by, ticket_id)`** —
  writes a `pending` row to `approvals`, reads `cash_accounts` for the affordability picture.
  **Moves no money.** This is the only payment path an agent has. Duplicate requests for the
  same obligation are rejected.
- **`list_payment_approvals(status)`** — `approvals`. What the human dashboard shows.
- **`decide_payment_approval(approval_id, decision, decided_by)`** — writes
  `approvals.status`/`decided_by`/`decided_at`. **HUMAN ONLY — withheld from every agent**
  (see §5.1).
- **`pay(approval_id)`** — writes `payments`, debits `cash_accounts.balance`, and updates the
  obligation (`invoices.status → paid`, or `leases.next_due` rolled forward a month). Refuses
  if the approval is not `approved` by a named human, and refuses if the amount exceeds the
  balance.

**Drafts — nothing is ever sent**

- **`save_draft(ticket_id, kind, audience, subject, body, created_by)`** — writes `drafts`.
  Customer messages, landlord replies and purchase orders stop here, on the board.
- **`list_drafts(ticket_id=None)`** — `drafts`. Lets an agent check a ticket has not already
  been answered before stacking a duplicate.

### 4.6 Every tool and the table it touches

R = reads, **W** = writes.

| # | Tool | `desk` | `tickets` | `inventory` | `pricing` | `vendors` | `invoices` | `leases` | `cash_accounts` | `payments` | `approvals`¹ | `drafts`¹ |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `list_open_tickets` | R | R | | | | | | | | | |
| 2 | `get_ticket` | R | R | R | R | | R | R | | | | |
| 3 | `resolve_ticket` | R | **W** | | | | | | | | | |
| 4 | `check_stock` | R | | R | | | | | | | | |
| 5 | `adjust_stock` | R | | **W** | | | | | | | | |
| 6 | `price_quote` | R | | | R | | | | | | | |
| 7 | `list_vendors` | | | | | R | | | | | | |
| 8 | `get_vendor_status` | R | | | | R | R | | | | | |
| 9 | `estimate_restock_eta` | R | | | | R | | | | | | |
| 10 | `get_rent_due` | R | | | | | | R | | | | |
| 11 | `get_cash_balance` | R | | | | | | | R | | | |
| 12 | `list_invoices` | R | | | | R | R | | | | | |
| 13 | `request_payment_approval` | R | | | | | | | R | | **W** | |
| 14 | `list_payment_approvals` | | | | | | | | | | R | |
| 15 | `decide_payment_approval` ⚠ | R | | | | | | | | | **W** | |
| 16 | `pay` | R | | | | | | **W** | **W** | **W** | **W** | |
| 17 | `save_draft` | R | | | | | | | | | | **W** |
| 18 | `list_drafts` | | | | | | | | | | | R |

¹ `approvals` and `drafts` are created in the **working copy only**, by the MCP server on
first use. The shop's original schema has nowhere to hold an approval queue or a message
that must not be sent, and the original `campus_customs.db` is never touched.

⚠ `decide_payment_approval` is the human's tool and is withheld from all five agents.

## 5. Safety

A prompt is a request, not a control. Anything that must always hold is enforced in code,
where the model cannot talk its way past it. The prompts then explain *why*, so the agents
do not spend turns fighting a guardrail they do not understand.

### 5.1 Guardrails a real business would require

**1. No agent can approve its own spending.** `decide_payment_approval` is listed in
`HUMAN_ONLY_TOOLS` in `backend/mcp_client.py` and filtered out before the toolset is handed
to any agent. All five agents are built from that filtered list, so the approve/reject switch
is reachable only from the human dashboard. Agents may *request* a payment; only a human may
authorise one.

**2. Payment requires a named human.** `pay()` refuses unless the approval row is in
`approved` status, and writes that human's name into `payments.approved_by`. A pending or
rejected approval is refused with `paid: false` and a reason. This is why, after the live run
below, `payments` is empty and the cash balance is untouched: the agents did the whole
analysis and queued two requests, and no money moved.

**3. Cash cannot go negative.** `pay()` compares the amount to the live balance and refuses
outright rather than clamping or partially paying. Since no revenue is modelled, an
overdraft would be unrecoverable.

**4. Stock cannot go negative.** `adjust_stock()` refuses a change that would leave fewer than
zero units, rather than flooring at zero — a silent floor would make the books claim stock
movements that never happened.

**5. Nothing reaches a real person.** There is no send path anywhere in the codebase. Customer
messages, landlord replies and purchase orders are written to `drafts` by `save_draft` and
stay on the board. No email client, no SMTP, no vendor API.

**6. No invented facts.** Every shop number comes from an MCP tool reading a row. A missing
row returns `found: false` with a message instead of a plausible guess, and the prompts tell
each agent that `found: false` *is* the answer. The backend never opens the database, so
there is no second path by which a number could enter without passing a tool.

**7. One clock.** Every date comparison uses `desk.date_today`. Overdue, due-soon and every
ETA are measured against the shop's calendar, so the system cannot drift as real time passes.

**8. Honest ETAs.** `get_vendor_status` reports `can_ship: false` for a vendor holding an open
invoice, and `estimate_restock_eta` takes a `from_date` so a blocked restock is quoted as
*payment date + lead days*. The guardrail here is against the most expensive failure in a real
shop: promising a customer a date the supply chain cannot meet.

**9. A full audit trail.** Every agent start, tool call with arguments and result, delegation,
refusal and finish is appended to `output/audit_trail.json` with timing and token cost. Any
database change can be traced to the agent, the ticket, and the tool call that made it.

**10. The original data is never touched.** The MCP server opens only
`campus_customs_new.db`. `data/campus_customs.db` is the reset point.

**What a real business would still need beyond this:** rate limits and spend caps per run,
a second approver above a dollar threshold, PII handling rules for customer records,
retention and deletion policy on the audit trail, an alert when an agent's refusal rate
spikes (a sign the data or the prompts have drifted), and a kill switch that halts the team
mid-run.

### 5.2 Constraints that control token usage

A fully connected team of five is a token bonfire if nothing bounds it — any agent can ask
any other, and those can ask back. The limits below are enforced by the framework, not
requested in prose.

| Constraint | Where | Value | What it prevents |
|---|---|---|---|
| Delegation depth | `DelegationBudget.max_depth` | 2 | A → B → C → D chains; a refusal at the limit tells the agent to answer with what it has |
| Delegations per run | `DelegationBudget.max_calls` | 12 | Two agents ping-ponging for the whole board |
| Specialist requests / tool calls | `llm.SPECIALIST_LIMITS` | 8 / 10 | A specialist looping on tools instead of answering |
| Boss requests / tool calls | `llm.BOSS_LIMITS` | 16 / 24 | A runaway ticket; `UsageLimitExceeded` is caught and logged, not crashed on |
| Structured output | `AgentOutput`, `TicketDecision` | — | Prose replies the next agent has to re-read and re-summarise; findings arrive as fields |
| One MCP session per run | `mcp_session()` | 1 | Re-handshaking a subprocess per tool call |
| Shared model client | `@lru_cache` on `build_model()` | 1 | Five clients where one will do |
| Pre-joined ticket reads | `get_ticket` | 1 call | Four separate lookups to assemble one ticket |
| Prompts tell agents not to re-fetch | all five prompt files | — | A delegate re-reading what the caller just read |

Both ceilings proved live rather than theoretical: the run below logged one
`delegation_refused` event when the budget was spent, and the agent completed the ticket with
the tools it had.

### 5.3 Live run — what actually happened

Full board, three tickets, model `gpt-6-luna`, reset database:

```
tool calls 57 | delegations 12 | tokens in 199,586 out 12,847
```

| Ticket | Outcome | Actions written |
|---|---|---|
| 101 | Left **open** — waiting on human approval | Approval #1 queued ($840, invoice 501); customer draft 1 saved, no dated ETA promised |
| 102 | Left **open** — waiting on human approval | Approval #2 queued ($2,400, lease 1); landlord draft 2 saved |
| 103 | **Resolved** | Customer draft 3 saved with pricing and the restock constraint |

Database state afterwards — the guardrails visible as data:

| Check | Result |
|---|---|
| `payments` rows | **0** — no money moved without a human |
| `cash_accounts.balance` | **$3,400.00** — unchanged |
| `invoices` 501 status | still **open** |
| `approvals` | 2 rows, both **pending**, `decided_by: null` |
| `drafts` | 3 rows, none sent |

Delegation actually used the full mesh — 7 distinct sender→receiver pairs, including three
that never pass through the Boss:

```
Boss → Accounting (3)   Boss → Inventory (2)   Boss → CustomerService (2)   Boss → Facilities (1)
Inventory → Accounting (2)   CustomerService → Facilities (1)   Facilities → Accounting (1)
```

Maximum depth reached: 2, which is the cap.

## 6. Backend routes

FastAPI, in `backend/main.py`. Started from the `backend/` directory with:

```bash
uvicorn main:app --reload --port 8000
```

Serving on `http://localhost:8000`, with CORS open to the Vite dev server so the React
dashboard can reach it. Every shop fact these routes return is read through the MCP server —
the only file-level database access in the backend is `/reset`, which copies a file.

| Route | What it does |
|---|---|
| `GET /tickets` | All three tickets with current status (open/resolved), each with its approvals and drafts attached |
| `GET /tickets/{id}` | One ticket with its inventory, pricing, lease and invoice rows joined in |
| `POST /tickets/{id}/run` | Hands that ticket to the agent team; returns a `run_id` immediately and works it in the background |
| `GET /runs` | Every run this process started, newest first, with status and the Boss's final decision |
| `GET /events` | Recent agent activity for the board to refresh on — agent, depth, ticket, tool, arguments, result, delegation, tokens; filterable by `run_id` and `since_seq` |
| `GET /drafts` | Messages and purchase orders the agents wrote; nothing here has been sent |
| `GET /approvals` | The payment approval queue the agents have asked a human to authorise |
| `POST /approvals/{id}/decide` | **The only route that moves money** — a named human approves or rejects, and on approval the payment executes immediately |
| `GET /cash` | Current `cash_accounts` balance, plus what has been paid out and what pending requests would cost |
| `POST /reset` | Restores the working database from the untouched original for a clean run; keeps the audit trail |
| `GET /health` | Confirms the backend can reach the MCP server; reports the model, tool count, and which tools are withheld from agents |

### 6.1 The approval route is the hinge

`POST /approvals/{id}/decide` is where the assignment's payment rule becomes real. Agents
can only reach `request_payment_approval`, which queues a request and moves nothing; the
`decide_payment_approval` tool is withheld from all five of them. This route is the human's
hand on that switch, and on `approve` it runs `pay` straight away — writing the `payments`
row stamped with the human's name, debiting the balance, and flipping the invoice to `paid`
or rolling the lease's due date forward.

Verified against the live backend:

| Test | Result |
|---|---|
| Approve invoice 501 ($840) as "Yookyung Eom" | Paid. `payments` row 1 with `approved_by: Yookyung Eom`; balance **$3,400 → $2,560**; invoice 501 → `paid` |
| Approve rent lease 1 ($2,400) | Paid. Balance **$2,560 → $160**; `leases.next_due` rolled forward |
| Approve a $500 payment against a $160 balance | **Refused** — `REFUSED: paying $500.00 from $160.00 would leave a negative balance.` Balance unchanged at $160 |
| Reject a queued request | `No money moved.` `payment: null` |
| `POST /reset` | Tickets back to open, cash back to $3,400.00, invoice 501 back to `open`, `payments` emptied — audit trail kept |
| Two runs at once | Second returns **HTTP 409**; one agent run at a time, so writes cannot interleave |

### 6.2 Why runs are backgrounded

A ticket is minutes of model time. `POST /tickets/{id}/run` returns a `run_id` at once and
the board polls `GET /events?run_id=…&since_seq=…` for new steps, which is both how the
dashboard stays live and why the browser never waits on an open request.

## 7. The dashboard

React + Vite + TypeScript, in `frontend/`. Started with `npm run dev`, served at
`http://localhost:5173`, talking to the backend at `http://localhost:8000`, which allows that
origin via CORS. Full design reasoning is in `output/design.md`; this is the structural
summary.

### 7.1 Layout — a desk, not an admin panel

Three columns, each with one job, in the order the task is actually performed:

| Column | What it is | What it does |
|---|---|---|
| **On the board** | Ticket cards, lightly rotated like a stack of paper slips | Lists all three tickets; click to select, "Hand to the team" to run one |
| **The wire** | The live feed down the centre | Every agent step as it happens, then the Boss's call and a per-agent summary |
| **The cash drawer** | Pinned right-hand panel | The checking balance, the paper tape, and the approval slips only a human can sign |

### 7.2 How the five agents read apart

Each agent carries three distinguishing signals so a speaker is identifiable from any one of
them: a reserved hue, a monogram, and position.

| Agent | Hue | Monogram |
|---|---|---|
| Boss | deep rose | **B** — *and the only agent whose name is set in the display serif* |
| Inventory | green | **I** |
| Accounting | ochre | **A** |
| Facilities | indigo | **F** |
| Customer Service | violet | **C** |
| The human | forest green, outside the agent palette | their initial |

Delegation depth is **drawn**: a delegated line indents 26px per level with a thread back to
whoever asked, so an agent-to-agent hand-off that never touched the Boss is visible at a
glance. Tool calls are rendered in shop English (*"checked vendor 1 — can they ship?"*) with
the exact tool name kept as a monospace chip, and the six write tools get an ochre chip rather
than a rose one. When an agent reports back, its conclusion gets a quote block — machinery and
speech look different.

### 7.3 Resolved tickets and cash

**Resolved** is a wax seal that presses onto the card with a scale-down animation, the card
washing pale and its button switching to "Run again". A ticket still waiting on a human
approval deliberately does **not** get the seal — it keeps a red `awaiting approval` tag,
because the work is not finished until someone signs.

**Cash** is the largest type on the page — 42px display serif with tabular numerals — and it
reddens and shakes when it falls. Beneath it a paper tape shows *paid out so far*, *awaiting
your call*, and **"left if you approve all"**, the figure a shopkeeper needs before deciding
rather than after.

The Approve button is disabled until the human types their own name, which is written
permanently into `payments.approved_by`. Printed under the queue, always visible:

> **No agent can approve a payment.** They can only prepare one — the tool that authorises
> money is kept off every agent's toolset and lives here, with you.

### 7.4 Live behaviour

`POST /tickets/{id}/run` returns a `run_id` immediately; the board polls
`GET /events?run_id=…&since_seq=…` every 1.2s so only new events cross the wire, and the feed
auto-scrolls. While a run is live every run button disables, matching the backend's
one-run-at-a-time rule rather than letting a click fail with HTTP 409.

## 8. The full board run

Model `gpt-6-luna` throughout. Database reset from the pristine original before the first
ticket, human approver **Yookyung Eom**. Driven end to end through the backend's own HTTP
routes by `scripts/full_run.py` — nothing bypassed the system under test.

### 8.1 The loop

A ticket blocked on money cannot finish in one pass, and that is the approval gate working:

1. **Hand the ticket to the team.** The agents analyse it and queue any payment it needs.
   They cannot pay; nothing moves.
2. **The human approves.** Cash moves here and only here.
3. **Hand it back.** The blocker is gone, so the Boss finishes the work and closes the ticket.

### 8.2 Results

| Ticket | Passes | Agents active | Final status | Cash |
|---|---|---|---|---|
| **101** Bulldog tee | 2 | Boss, Inventory, Accounting, Customer Service | **resolved** | $3,400.00 → $2,560.00 (−$840.00) |
| **102** Rent due | 2 | Boss, Facilities, Accounting, Customer Service | **resolved** | $2,560.00 → $160.00 (−$2,400.00) |
| **103** Bulk discount | 1 | Boss, Accounting, Inventory, Customer Service | **resolved** | $160.00 → $160.00 (no change) |

**Delegations observed** — including three hops that never passed through the Boss:

```
101: Boss→Inventory  Boss→Accounting  Boss→CustomerService
     Inventory→Accounting        CustomerService→Inventory
102: Boss→Facilities  Boss→CustomerService
     Facilities→Accounting
103: Boss→Accounting  Boss→Inventory  Boss→CustomerService
     CustomerService→Accounting  CustomerService→Inventory
```

Customer Service delegating *before* drafting was unplanned and is the most interesting
behaviour in the run: it refused to put a number in a customer's message that it had not
verified itself.

### 8.3 Cash — the whole ledger

| | Amount |
|---|---|
| Opening balance after reset | **$3,400.00** |
| Ticket 101 — invoice 501 to Bulldog Print Co, approval #1 | −$840.00 |
| Ticket 102 — rent on lease 1 to Elm City Properties, approval #2 | −$2,400.00 |
| Ticket 103 — no payment required | $0.00 |
| **Closing balance** | **$160.00** |

`$3,400.00 − $3,240.00 = $160.00`, and `cash_accounts.checking` in
`data/campus_customs_new.db` reads **$160.00**. The build scripts assert this and refuse to
write their output files if it does not hold.

Both `payments` rows carry `approved_by = "Yookyung Eom"`. **There is no payment in this
database that a human did not authorise.**

Downstream obligations updated by `pay`: invoice 501 → `paid`; lease 1 `next_due`
2026-09-02 → 2026-10-02.

### 8.4 What the agents produced

Five drafts, **none sent** — there is no send path in the codebase:

| Draft | Ticket | Kind | To | By |
|---|---|---|---|---|
| 1 | 101 | customer message | Tauhid Zaman | Customer Service |
| 2 | 101 | customer message (revised after payment cleared) | Tauhid Zaman | Boss |
| 3 | 101 | **purchase order** | Bulldog Print Co | Boss |
| 4 | 102 | landlord message | Elm City Properties | Customer Service |
| 5 | 103 | customer message | Yale AI Club | Customer Service |

Two judgments worth recording, both visible on the wire:

- **Ticket 102 — the agents caught the landlord's error.** Facilities reported: *"The lease of
  record governs: rent for the Chapel Street shop is $2,400, due 2026-10-02, which is 32 days
  away as of 2026-08-31. The ticket email's 'due in 2 days' conflicts with the lease."* The
  draft asks the landlord to confirm or correct the notice rather than accepting it.
- **Ticket 103 — no discount was invented.** Accounting reported the $58.00 list, the $22.00
  cost floor and the 62.1% margin, and declined to quote a bulk price because the club named
  no target. The draft asks for their proposed price instead of guessing one.

### 8.5 Where this run is recorded

| File | What it holds |
|---|---|
| `output/audit_trail.json` | Every agent step from this run, appended to the earlier history |
| `output/run_log.json` | The driver's view: passes, approvals, and cash at each step |
| `output/resolved_tickets.json` | Per ticket: id, final status, outcome, each agent's contribution, human approvals |
| `output/desk_tickets.html` | Expected (Problem 6) beside Actual, plus the itemised Cash tab and the Reflection |
| `output/resolved_board.html` | The finished board with a screenshot of the React desk per ticket |

### 8.6 Plan versus reality

The Problem 6 forecast was written before any agent ran, and the comparison is in the
Reflection tab of `desk_tickets.html`. In short:

**Right:** all three first contacts (101 → Inventory, 102 → Facilities, 103 → Accounting);
ticket 102's entire delegation chain; the Inventory → Accounting hop on 101; the narrow
routing on every ticket; the shared Bulldog Print Co bottleneck; and the $160 closing figure.

**Wrong:** ticket 103 reached Inventory via the Boss rather than via Accounting; Customer
Service delegated before drafting, which was not foreseen at all; ticket 101 produced three
drafts including an unanticipated purchase order; and no ticket needing payment could ever
have closed in the single pass the plan implicitly assumed.

---

## 9. Where everything lives

| Path | What it is |
|---|---|
| `data/campus_customs.db` | The pristine original. Never opened by the server; the reset point. |
| `data/campus_customs_new.db` | The working copy. All reads and writes land here. |
| `.mcp.json` | MCP server registration (stdio) |
| `mcp_server/server.py` | 18 FastMCP tools — the only route to shop facts (§4) |
| `mcp_server/README.md` | Server purpose, database file, full tool list |
| `backend/llm.py` | The one line that names a model: `gpt-6-luna` (§3.1) |
| `backend/models.py` | Agent output types, run context, delegation budget, audit records |
| `backend/mcp_client.py` | MCP session; builds agent tools from the server's schemas; withholds the human-only tool |
| `backend/agents.py` | The five agents and the full delegation mesh (§3) |
| `backend/prompts/*.md` | One prompt per agent, carrying that agent's shop rules |
| `backend/audit.py` | Append-only trail writer |
| `backend/main.py` | 11 FastAPI routes (§6) |
| `frontend/` | The React desk (§7) |
| `scripts/mcp_smoke_test.py` | Tests every MCP tool over a real stdio session |
| `scripts/full_run.py` | Drives a complete board run through the HTTP routes |
| `scripts/build_outputs.py` · `build_desk_tickets.py` · `build_board_page.py` | Generate the output files, asserting the cash reconciles |
