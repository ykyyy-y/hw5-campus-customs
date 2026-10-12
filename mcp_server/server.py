"""Campus Customs MCP server.

Every agent on the Campus Customs team reaches the shop database through this server.
It is the single read/write boundary for the shop: no agent opens SQLite directly, and
no tool here invents a value. Anything a tool returns was read out of
``data/campus_customs_new.db``; when a row does not exist, the tool returns
``found: False`` rather than guessing a stock level, a rent amount, or a price.

Two agent-side tables are created in the working copy on first use, because the shop's
original schema has nowhere to put them: ``approvals`` (the human approval queue that
gates every payment) and ``drafts`` (customer messages and purchase orders, which stay
on the board and are never sent).

Safety rules enforced in code, not left to the model:

* ``pay`` refuses unless an ``approvals`` row for that exact payment is ``approved`` by
  a named human, and refuses again if the payment would push the cash balance below zero.
* ``decide_payment_approval`` is the human's tool. It is excluded from the agent toolset
  in ``backend/mcp_client.py``, so no agent can approve its own payment request.
* "Today" is ``desk.date_today``, never the real wall clock.
* ETAs are built from ``vendors.lead_days``; a vendor with an open unpaid invoice is
  reported as unable to ship.

Run::

    .venv/Scripts/python.exe mcp_server/server.py
"""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

# The working copy. data/campus_customs.db is the pristine original and is never opened
# here, so a run can always be reset from it.
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "campus_customs_new.db"

mcp = FastMCP("campus-customs")

# Tables the agent workflow needs that the shop's original schema does not provide.
# Created in the working copy only.
AGENT_TABLES = """
CREATE TABLE IF NOT EXISTS approvals (
    id           INTEGER PRIMARY KEY,
    ticket_id    INTEGER,
    kind         TEXT    NOT NULL,
    ref_id       INTEGER,
    amount       REAL    NOT NULL,
    reason       TEXT,
    status       TEXT    NOT NULL,
    requested_by TEXT    NOT NULL,
    requested_at TEXT    NOT NULL,
    decided_by   TEXT,
    decided_at   TEXT,
    payment_id   INTEGER
);

CREATE TABLE IF NOT EXISTS drafts (
    id         INTEGER PRIMARY KEY,
    ticket_id  INTEGER,
    kind       TEXT NOT NULL,
    audience   TEXT NOT NULL,
    subject    TEXT NOT NULL,
    body       TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(AGENT_TABLES)
    return conn


def _today(conn: sqlite3.Connection) -> str:
    """The shop's today, read from ``desk.date_today`` — never the real wall clock."""
    return conn.execute("SELECT date_today FROM desk LIMIT 1").fetchone()["date_today"]


def _days_between(start: str, end: str) -> int:
    return (date.fromisoformat(end) - date.fromisoformat(start)).days


def _add_days(start: str, days: int) -> str:
    return (date.fromisoformat(start) + timedelta(days=days)).isoformat()


# =============================================================================
# The ticket board
# =============================================================================
@mcp.tool
def list_open_tickets() -> dict[str, Any]:
    """List every ticket still on the board, with the shop's today.

    Reads ``tickets`` (and ``desk`` for the date). This is the Boss's entry point: it is
    how a run discovers what work exists instead of being told.

    Returns:
        ``today``, ``count``, and the open ticket rows in arrival order.
    """
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, type, requester, subject, sku, size, qty, lease_id, invoice_id, "
            "status, notes, created_at FROM tickets WHERE status = 'open' "
            "ORDER BY created_at, id"
        ).fetchall()
        return {
            "today": _today(conn),
            "count": len(rows),
            "tickets": [dict(r) for r in rows],
        }


@mcp.tool
def get_ticket(ticket_id: int) -> dict[str, Any]:
    """Pull one ticket with the rows it points at already joined in.

    Reads ``tickets``, and follows its foreign keys into ``inventory`` (via sku+size),
    ``pricing`` (via sku), ``leases`` (via lease_id) and ``invoices`` (via invoice_id),
    so an agent sees the whole dependency in one call instead of four.

    Args:
        ticket_id: The ticket id, e.g. ``101``.
    """
    with _connect() as conn:
        row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if row is None:
            return {"found": False, "ticket_id": ticket_id,
                    "message": f"No ticket exists with id {ticket_id}."}

        ticket = dict(row)
        linked: dict[str, Any] = {}

        if ticket["sku"] and ticket["size"]:
            inv = conn.execute(
                "SELECT sku, name, size, qty, location FROM inventory "
                "WHERE sku = ? AND size = ?", (ticket["sku"], ticket["size"]),
            ).fetchone()
            linked["inventory"] = dict(inv) if inv else None
        if ticket["sku"]:
            pr = conn.execute(
                "SELECT sku, unit_cost, list_price FROM pricing WHERE sku = ?",
                (ticket["sku"],),
            ).fetchone()
            linked["pricing"] = dict(pr) if pr else None
        if ticket["lease_id"]:
            ls = conn.execute(
                "SELECT * FROM leases WHERE id = ?", (ticket["lease_id"],)
            ).fetchone()
            linked["lease"] = dict(ls) if ls else None
        if ticket["invoice_id"]:
            iv = conn.execute(
                "SELECT i.*, v.name AS vendor_name FROM invoices i "
                "JOIN vendors v ON v.id = i.vendor_id WHERE i.id = ?",
                (ticket["invoice_id"],),
            ).fetchone()
            linked["invoice"] = dict(iv) if iv else None

        return {"found": True, "today": _today(conn), "ticket": ticket, "linked": linked}


@mcp.tool
def resolve_ticket(ticket_id: int, resolution: str, resolved_by: str) -> dict[str, Any]:
    """Close a ticket and append the resolution to its notes.

    Writes ``tickets.status`` and ``tickets.notes``. Only called once the work the ticket
    describes has actually happened, so the board reflects reality.

    Args:
        ticket_id: Ticket to close.
        resolution: What was decided or done, in one or two sentences.
        resolved_by: The agent closing it, e.g. ``Boss``.
    """
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, status, notes FROM tickets WHERE id = ?", (ticket_id,)
        ).fetchone()
        if row is None:
            return {"ok": False, "ticket_id": ticket_id,
                    "message": f"No ticket exists with id {ticket_id}."}
        if row["status"] != "open":
            return {"ok": False, "ticket_id": ticket_id, "status": row["status"],
                    "message": f"Ticket {ticket_id} is already {row['status']}."}

        today = _today(conn)
        notes = f"{row['notes'] or ''}\n[{today}] resolved by {resolved_by}: {resolution}".strip()
        conn.execute(
            "UPDATE tickets SET status = 'resolved', notes = ? WHERE id = ?",
            (notes, ticket_id),
        )
        conn.commit()
        return {"ok": True, "ticket_id": ticket_id, "status": "resolved",
                "resolved_by": resolved_by, "resolved_on": today}


# =============================================================================
# Inventory
# =============================================================================
@mcp.tool
def check_stock(sku: str, size: str, qty_wanted: int = 1) -> dict[str, Any]:
    """Look up on-hand units for one (sku, size) and report the shortfall.

    Reads ``inventory``. Stock is keyed by (sku, size), so this is the only honest way to
    answer "can we fill this line?".

    Unblocks ticket 101 (CC-TEE-WHITE in size S): it turns the request into a number the
    Inventory agent can act on instead of a guess.

    Args:
        sku: Product code, e.g. ``CC-TEE-WHITE``.
        size: Size code as stored in inventory, e.g. ``S``, ``M``, ``OS``.
        qty_wanted: Units the ticket asks for. Defaults to 1.
    """
    with _connect() as conn:
        row = conn.execute(
            "SELECT sku, name, size, qty, location FROM inventory WHERE sku = ? AND size = ?",
            (sku, size),
        ).fetchone()
        if row is None:
            return {"found": False, "sku": sku, "size": size,
                    "message": f"No inventory row exists for ({sku}, {size})."}

        on_hand = row["qty"]
        shortfall = max(0, qty_wanted - on_hand)
        return {
            "found": True, "sku": row["sku"], "name": row["name"], "size": row["size"],
            "on_hand": on_hand, "location": row["location"], "qty_wanted": qty_wanted,
            "can_fill": shortfall == 0, "shortfall": shortfall, "as_of": _today(conn),
        }


@mcp.tool
def adjust_stock(sku: str, size: str, delta: int, reason: str, changed_by: str) -> dict[str, Any]:
    """Move stock up or down for one (sku, size), refusing to go negative.

    Writes ``inventory.qty``. Used to decrement stock when an order is actually filled,
    or to receive units when a restock lands. A ``delta`` that would drive quantity below
    zero is refused rather than clamped, so the books never claim stock that never existed.

    Args:
        sku: Product code.
        size: Size code.
        delta: Signed change, e.g. ``-1`` to fulfil one unit.
        reason: Why the stock moved, recorded for the audit trail.
        changed_by: The agent making the change.
    """
    with _connect() as conn:
        row = conn.execute(
            "SELECT qty FROM inventory WHERE sku = ? AND size = ?", (sku, size)
        ).fetchone()
        if row is None:
            return {"ok": False, "sku": sku, "size": size,
                    "message": f"No inventory row exists for ({sku}, {size})."}

        before = row["qty"]
        after = before + delta
        if after < 0:
            return {"ok": False, "sku": sku, "size": size, "qty_before": before,
                    "attempted_delta": delta,
                    "message": f"Refused: {before} on hand, {delta} would leave {after}. "
                               "Stock cannot go negative."}

        conn.execute(
            "UPDATE inventory SET qty = ? WHERE sku = ? AND size = ?", (after, sku, size)
        )
        conn.commit()
        return {"ok": True, "sku": sku, "size": size, "qty_before": before,
                "qty_after": after, "delta": delta, "reason": reason,
                "changed_by": changed_by, "changed_on": _today(conn)}


# =============================================================================
# Pricing
# =============================================================================
@mcp.tool
def price_quote(sku: str, qty: int, proposed_unit_price: float | None = None) -> dict[str, Any]:
    """Price a quantity at list, and test a proposed discount against the cost floor.

    Reads ``pricing`` for ``unit_cost`` and ``list_price``. The cost floor it reports is
    the stored ``unit_cost`` itself — nothing is marked up or assumed.

    Unblocks ticket 103 (bulk discount on 20 CC-HOOD-NAVY in size M): it gives Accounting
    the margin on the full-price order and an immediate pass/fail on any discounted price,
    so a discount is approved on arithmetic rather than on goodwill.

    Args:
        sku: Product code, e.g. ``CC-HOOD-NAVY``.
        qty: Units requested on the ticket.
        proposed_unit_price: Optional discounted per-unit price to evaluate.
    """
    with _connect() as conn:
        row = conn.execute(
            "SELECT sku, unit_cost, list_price FROM pricing WHERE sku = ?", (sku,)
        ).fetchone()
        if row is None:
            return {"found": False, "sku": sku,
                    "message": f"No pricing row exists for {sku}."}

        unit_cost, list_price = row["unit_cost"], row["list_price"]
        total_cost = round(unit_cost * qty, 2)
        list_revenue = round(list_price * qty, 2)

        result: dict[str, Any] = {
            "found": True, "sku": row["sku"], "qty": qty,
            "unit_cost": unit_cost, "list_price": list_price,
            "total_cost": total_cost, "list_revenue": list_revenue,
            "list_margin": round(list_revenue - total_cost, 2),
            "list_margin_pct": round((list_price - unit_cost) / list_price * 100, 1),
            "cost_floor_unit_price": unit_cost,
            "max_discount_pct_before_cost": round((list_price - unit_cost) / list_price * 100, 1),
            "as_of": _today(conn),
        }

        if proposed_unit_price is not None:
            proposed_revenue = round(proposed_unit_price * qty, 2)
            result |= {
                "proposed_unit_price": proposed_unit_price,
                "proposed_discount_pct": round(
                    (list_price - proposed_unit_price) / list_price * 100, 1),
                "proposed_revenue": proposed_revenue,
                "proposed_margin": round(proposed_revenue - total_cost, 2),
                "proposed_margin_pct": round(
                    (proposed_unit_price - unit_cost) / proposed_unit_price * 100, 1)
                if proposed_unit_price else None,
                "above_cost": proposed_unit_price > unit_cost,
            }
        return result


# =============================================================================
# Vendors
# =============================================================================
@mcp.tool
def list_vendors() -> dict[str, Any]:
    """List every vendor with its specialty and lead time.

    Reads ``vendors``. The specialty is how a shortfall is matched to a supplier, and
    ``lead_days`` is the only legitimate source of an ETA.
    """
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, name, specialty, lead_days FROM vendors ORDER BY id"
        ).fetchall()
        return {"count": len(rows), "vendors": [dict(r) for r in rows]}


@mcp.tool
def get_vendor_status(vendor_id: int) -> dict[str, Any]:
    """Report whether a vendor can ship, and what its ETA would be.

    Reads ``vendors`` for the lead time and ``invoices`` for that vendor's unpaid bills,
    plus ``desk.date_today`` to date the ETA. A vendor holding any open invoice is
    reported as ``can_ship: false`` with the blocking invoices listed, because the shop's
    rule is that a vendor will not ship new product while unpaid.

    Args:
        vendor_id: The vendor id, e.g. ``1`` for Bulldog Print Co.
    """
    with _connect() as conn:
        vendor = conn.execute(
            "SELECT id, name, specialty, lead_days FROM vendors WHERE id = ?", (vendor_id,)
        ).fetchone()
        if vendor is None:
            return {"found": False, "vendor_id": vendor_id,
                    "message": f"No vendor exists with id {vendor_id}."}

        today = _today(conn)
        open_invoices = [
            dict(r) for r in conn.execute(
                "SELECT id, amount, due_date, status, description FROM invoices "
                "WHERE vendor_id = ? AND status = 'open' ORDER BY due_date", (vendor_id,)
            ).fetchall()
        ]
        for inv in open_invoices:
            inv["days_overdue"] = max(0, -_days_between(today, inv["due_date"]))

        can_ship = not open_invoices
        return {
            "found": True, "vendor_id": vendor["id"], "name": vendor["name"],
            "specialty": vendor["specialty"], "lead_days": vendor["lead_days"],
            "today": today, "can_ship": can_ship,
            "open_invoices": open_invoices,
            "open_invoice_total": round(sum(i["amount"] for i in open_invoices), 2),
            "eta_if_ordered_today": _add_days(today, vendor["lead_days"]) if can_ship else None,
            "blocking_reason": None if can_ship else (
                f"{vendor['name']} holds {len(open_invoices)} open invoice(s) totalling "
                f"${sum(i['amount'] for i in open_invoices):,.2f} and will not ship until paid."
            ),
        }


@mcp.tool
def estimate_restock_eta(vendor_id: int, from_date: str | None = None) -> dict[str, Any]:
    """Date a delivery from a vendor's lead time, optionally from a later start date.

    Reads ``vendors.lead_days`` and ``desk.date_today``. When a restock cannot start until
    an invoice is paid, pass that payment date as ``from_date`` so the ETA quoted to a
    customer is payment date + lead days, not today + lead days.

    Args:
        vendor_id: The vendor id.
        from_date: ISO date the order can actually be placed. Defaults to the shop's today.
    """
    with _connect() as conn:
        vendor = conn.execute(
            "SELECT id, name, lead_days FROM vendors WHERE id = ?", (vendor_id,)
        ).fetchone()
        if vendor is None:
            return {"found": False, "vendor_id": vendor_id,
                    "message": f"No vendor exists with id {vendor_id}."}

        today = _today(conn)
        start = from_date or today
        return {"found": True, "vendor_id": vendor["id"], "vendor_name": vendor["name"],
                "lead_days": vendor["lead_days"], "today": today, "order_placed_on": start,
                "eta": _add_days(start, vendor["lead_days"])}


# =============================================================================
# Facilities
# =============================================================================
@mcp.tool
def get_rent_due(lease_id: int) -> dict[str, Any]:
    """Return the rent amount and due date for one lease, dated against the shop's today.

    Reads ``leases`` for the amount and due date, and ``desk.date_today`` for the
    reference date used to compute ``days_until_due``.

    Unblocks ticket 102 (Elm City Properties, "rent due in 2 days"): the amount and date
    come from the lease of record rather than from the landlord's email.

    Args:
        lease_id: The lease id carried on the ticket, e.g. ``1``.
    """
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, space_name, landlord, monthly_rent, next_due, notes "
            "FROM leases WHERE id = ?", (lease_id,),
        ).fetchone()
        if row is None:
            return {"found": False, "lease_id": lease_id,
                    "message": f"No lease exists with id {lease_id}."}

        today = _today(conn)
        days = _days_between(today, row["next_due"])
        return {"found": True, "lease_id": row["id"], "space_name": row["space_name"],
                "landlord": row["landlord"], "monthly_rent": row["monthly_rent"],
                "next_due": row["next_due"], "notes": row["notes"], "today": today,
                "days_until_due": days, "is_overdue": days < 0}


# =============================================================================
# Money
# =============================================================================
@mcp.tool
def get_cash_balance(account: str = "checking") -> dict[str, Any]:
    """Return the current cash balance for one account.

    Reads ``cash_accounts``. This is the hard ceiling on everything the team can commit
    to: no revenue is modelled in this shop, so money only ever leaves.

    Args:
        account: Account name. Defaults to ``checking``.
    """
    with _connect() as conn:
        row = conn.execute(
            "SELECT name, balance, date FROM cash_accounts WHERE name = ?", (account,)
        ).fetchone()
        if row is None:
            return {"found": False, "account": account,
                    "message": f"No cash account named {account}."}
        return {"found": True, "account": row["name"], "balance": row["balance"],
                "as_of": row["date"], "today": _today(conn)}


@mcp.tool
def list_invoices(status: str = "open") -> dict[str, Any]:
    """List invoices by status, with the vendor name and days overdue.

    Reads ``invoices`` joined to ``vendors``, with ``desk.date_today`` as the reference
    for overdue. An open invoice is what freezes a vendor, so this is how Accounting finds
    out why a restock is blocked.

    Args:
        status: ``open``, ``paid``, or ``all``. Defaults to ``open``.
    """
    with _connect() as conn:
        today = _today(conn)
        sql = ("SELECT i.id, i.vendor_id, v.name AS vendor_name, i.amount, i.due_date, "
               "i.status, i.description FROM invoices i JOIN vendors v ON v.id = i.vendor_id")
        rows = (conn.execute(sql + " ORDER BY i.due_date").fetchall() if status == "all"
                else conn.execute(sql + " WHERE i.status = ? ORDER BY i.due_date",
                                  (status,)).fetchall())
        invoices = []
        for r in rows:
            inv = dict(r)
            inv["days_overdue"] = max(0, -_days_between(today, inv["due_date"]))
            inv["is_overdue"] = inv["days_overdue"] > 0
            invoices.append(inv)
        return {"today": today, "status_filter": status, "count": len(invoices),
                "total_amount": round(sum(i["amount"] for i in invoices), 2),
                "invoices": invoices}


@mcp.tool
def request_payment_approval(
    kind: str, ref_id: int, amount: float, reason: str,
    requested_by: str, ticket_id: int | None = None,
) -> dict[str, Any]:
    """Queue a payment for a human to approve. This does NOT move any money.

    Writes a ``pending`` row to ``approvals``, and reads ``cash_accounts`` so the request
    carries the affordability picture the human needs. This is the only way an agent can
    start a payment: agents can request, humans decide, and only then can ``pay`` run.

    Args:
        kind: ``invoice`` or ``rent``.
        ref_id: The invoice id (for ``invoice``) or lease id (for ``rent``).
        amount: Amount to pay, taken from the invoice or lease row, never estimated.
        reason: Why this should be paid now, including what it unblocks.
        requested_by: The agent raising the request.
        ticket_id: The ticket this payment serves, when there is one.
    """
    if kind not in {"invoice", "rent"}:
        return {"ok": False, "message": f"kind must be 'invoice' or 'rent', got '{kind}'."}
    if amount <= 0:
        return {"ok": False, "message": f"Refused: amount must be positive, got {amount}."}

    with _connect() as conn:
        today = _today(conn)
        balance = conn.execute(
            "SELECT balance FROM cash_accounts WHERE name = 'checking'"
        ).fetchone()["balance"]

        # Reject a duplicate request for the same obligation rather than stacking them.
        dup = conn.execute(
            "SELECT id FROM approvals WHERE kind = ? AND ref_id = ? "
            "AND status IN ('pending', 'approved', 'paid')", (kind, ref_id),
        ).fetchone()
        if dup is not None:
            return {"ok": False, "existing_approval_id": dup["id"],
                    "message": f"Approval {dup['id']} already covers {kind} {ref_id}; "
                               "not queuing a duplicate."}

        cur = conn.execute(
            "INSERT INTO approvals (ticket_id, kind, ref_id, amount, reason, status, "
            "requested_by, requested_at) VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)",
            (ticket_id, kind, ref_id, amount, reason, requested_by, today),
        )
        conn.commit()
        return {
            "ok": True, "approval_id": cur.lastrowid, "status": "pending",
            "kind": kind, "ref_id": ref_id, "amount": amount, "ticket_id": ticket_id,
            "requested_by": requested_by, "requested_at": today,
            "cash_balance_now": balance,
            "balance_after_if_paid": round(balance - amount, 2),
            "affordable": amount <= balance,
            "note": "No money has moved. A human must approve this before pay() will run.",
        }


@mcp.tool
def list_payment_approvals(status: str = "all") -> dict[str, Any]:
    """List the payment approval queue, so a human can see what is waiting.

    Reads ``approvals``. This is what the dashboard shows the human who has to decide.

    Args:
        status: ``pending``, ``approved``, ``rejected``, ``paid``, or ``all``.
    """
    with _connect() as conn:
        rows = (conn.execute("SELECT * FROM approvals ORDER BY id").fetchall()
                if status == "all" else
                conn.execute("SELECT * FROM approvals WHERE status = ? ORDER BY id",
                             (status,)).fetchall())
        return {"status_filter": status, "count": len(rows),
                "approvals": [dict(r) for r in rows]}


@mcp.tool
def decide_payment_approval(approval_id: int, decision: str, decided_by: str) -> dict[str, Any]:
    """HUMAN ONLY. Approve or reject a queued payment.

    Writes ``approvals.status``, ``decided_by`` and ``decided_at``. This tool is withheld
    from every agent in ``backend/mcp_client.py`` — it is reachable only from the human
    dashboard, so no agent can approve its own payment request.

    Args:
        approval_id: The approval row to decide.
        decision: ``approve`` or ``reject``.
        decided_by: Name of the human deciding. Recorded on the payment.
    """
    if decision not in {"approve", "reject"}:
        return {"ok": False, "message": "decision must be 'approve' or 'reject'."}
    if not decided_by or not decided_by.strip():
        return {"ok": False, "message": "Refused: a named human approver is required."}

    with _connect() as conn:
        row = conn.execute("SELECT * FROM approvals WHERE id = ?", (approval_id,)).fetchone()
        if row is None:
            return {"ok": False, "message": f"No approval exists with id {approval_id}."}
        if row["status"] != "pending":
            return {"ok": False, "approval_id": approval_id, "status": row["status"],
                    "message": f"Approval {approval_id} is already {row['status']}."}

        today = _today(conn)
        new_status = "approved" if decision == "approve" else "rejected"
        conn.execute(
            "UPDATE approvals SET status = ?, decided_by = ?, decided_at = ? WHERE id = ?",
            (new_status, decided_by.strip(), today, approval_id),
        )
        conn.commit()
        return {"ok": True, "approval_id": approval_id, "status": new_status,
                "decided_by": decided_by.strip(), "decided_at": today}


@mcp.tool
def pay(approval_id: int) -> dict[str, Any]:
    """Execute a payment that a human has already approved.

    Writes ``payments`` (one row, stamped with the human's name in ``approved_by``),
    debits ``cash_accounts.balance``, and updates the obligation: an ``invoice`` payment
    flips ``invoices.status`` to ``paid``; a ``rent`` payment rolls ``leases.next_due``
    forward one month.

    Refuses, without moving money, when:

    * the approval is not in ``approved`` status (no human sign-off → no payment);
    * the amount exceeds the cash balance (the balance may never go negative).

    Args:
        approval_id: The approved request to execute.
    """
    with _connect() as conn:
        ap = conn.execute("SELECT * FROM approvals WHERE id = ?", (approval_id,)).fetchone()
        if ap is None:
            return {"ok": False, "paid": False,
                    "message": f"No approval exists with id {approval_id}."}
        if ap["status"] == "paid":
            return {"ok": False, "paid": False, "approval_id": approval_id,
                    "message": f"Approval {approval_id} has already been paid."}
        if ap["status"] != "approved":
            return {"ok": False, "paid": False, "approval_id": approval_id,
                    "status": ap["status"],
                    "message": f"REFUSED: approval {approval_id} is '{ap['status']}'. "
                               "A human must approve a payment before it can be made."}

        today = _today(conn)
        account = "checking"
        balance = conn.execute(
            "SELECT balance FROM cash_accounts WHERE name = ?", (account,)
        ).fetchone()["balance"]
        amount = ap["amount"]

        if amount > balance:
            return {"ok": False, "paid": False, "approval_id": approval_id,
                    "amount": amount, "balance": balance,
                    "message": f"REFUSED: paying ${amount:,.2f} from ${balance:,.2f} would "
                               "leave a negative balance. Cash balances may not go below zero."}

        cur = conn.execute(
            "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (ap["kind"], ap["ref_id"], amount, account, today, ap["decided_by"]),
        )
        payment_id = cur.lastrowid
        new_balance = round(balance - amount, 2)
        conn.execute(
            "UPDATE cash_accounts SET balance = ?, date = ? WHERE name = ?",
            (new_balance, today, account),
        )

        obligation: dict[str, Any] = {}
        if ap["kind"] == "invoice":
            conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (ap["ref_id"],))
            obligation = {"invoice_id": ap["ref_id"], "invoice_status": "paid"}
        elif ap["kind"] == "rent":
            lease = conn.execute(
                "SELECT next_due FROM leases WHERE id = ?", (ap["ref_id"],)
            ).fetchone()
            if lease is not None:
                due = date.fromisoformat(lease["next_due"])
                month, year = (due.month % 12) + 1, due.year + (1 if due.month == 12 else 0)
                next_due = date(year, month, min(due.day, 28)).isoformat()
                conn.execute("UPDATE leases SET next_due = ? WHERE id = ?",
                             (next_due, ap["ref_id"]))
                obligation = {"lease_id": ap["ref_id"], "next_due_was": lease["next_due"],
                              "next_due_now": next_due}

        conn.execute("UPDATE approvals SET status = 'paid', payment_id = ? WHERE id = ?",
                     (payment_id, approval_id))
        conn.commit()

        return {"ok": True, "paid": True, "payment_id": payment_id,
                "approval_id": approval_id, "kind": ap["kind"], "ref_id": ap["ref_id"],
                "amount": amount, "account": account, "paid_at": today,
                "approved_by": ap["decided_by"], "balance_before": balance,
                "balance_after": new_balance, "obligation_updated": obligation}


# =============================================================================
# Drafts — these stay on the board and are never sent
# =============================================================================
@mcp.tool
def save_draft(ticket_id: int, kind: str, audience: str, subject: str,
               body: str, created_by: str) -> dict[str, Any]:
    """Save a message or purchase order as a draft on the board. Nothing is sent.

    Writes ``drafts``. The shop's rule is that no customer is emailed and no vendor is
    called, so every outbound communication the team produces stops here, where a human
    can read it on the dashboard.

    Args:
        ticket_id: The ticket this draft answers.
        kind: ``customer_message``, ``landlord_message``, or ``purchase_order``.
        audience: Who it is addressed to, e.g. ``Tauhid Zaman``.
        subject: Subject line.
        body: Full text of the draft.
        created_by: The agent that wrote it.
    """
    with _connect() as conn:
        today = _today(conn)
        cur = conn.execute(
            "INSERT INTO drafts (ticket_id, kind, audience, subject, body, created_by, "
            "created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (ticket_id, kind, audience, subject, body, created_by, today),
        )
        conn.commit()
        return {"ok": True, "draft_id": cur.lastrowid, "ticket_id": ticket_id, "kind": kind,
                "audience": audience, "created_by": created_by, "created_at": today,
                "sent": False, "note": "Draft saved to the board. Nothing was sent."}


@mcp.tool
def list_drafts(ticket_id: int | None = None) -> dict[str, Any]:
    """List saved drafts, optionally for one ticket.

    Reads ``drafts``. Lets an agent check what has already been written before drafting
    again, and lets the dashboard show the human every pending message.

    Args:
        ticket_id: Restrict to one ticket. Omit for all drafts.
    """
    with _connect() as conn:
        rows = (conn.execute("SELECT * FROM drafts ORDER BY id").fetchall()
                if ticket_id is None else
                conn.execute("SELECT * FROM drafts WHERE ticket_id = ? ORDER BY id",
                             (ticket_id,)).fetchall())
        return {"count": len(rows), "drafts": [dict(r) for r in rows]}


if __name__ == "__main__":
    mcp.run()
