"""Build `output/resolved_tickets.json` from the real run.

Reads three sources and cross-checks them against each other:

* `output/run_log.json` — what the driver saw at each step, including the cash position
  before and after every ticket
* `output/audit_trail.json` — every agent step, so each agent's contribution is derived from
  what it actually called, not from what the Boss said about it
* the live backend — the final ticket statuses, the payments, and the closing balance

The closing balance is asserted against `cash_accounts` in the working database. If the
itemised cash movements do not sum to the real balance, this script fails rather than
writing a file that looks tidy and is wrong.
"""

from __future__ import annotations

import json
import sqlite3
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"
API = "http://localhost:8000"
DB = ROOT / "data" / "campus_customs_new.db"

AGENT_LABEL = {
    "Boss": "Boss",
    "Inventory": "Inventory",
    "Accounting": "Accounting",
    "Facilities": "Facilities",
    "CustomerService": "Customer Service",
}


def get(path: str) -> Any:
    with urllib.request.urlopen(f"{API}{path}", timeout=60) as r:
        return json.loads(r.read())


def db_rows(sql: str) -> list[dict]:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql)]
    finally:
        conn.close()


def contributions(events: list[dict], run_ids: set[str], ticket_id: int) -> list[dict]:
    """What each agent actually did on this ticket, derived from the audit trail."""
    rows: dict[str, dict[str, Any]] = {}

    for e in events:
        if e.get("run_id") not in run_ids:
            continue
        if e.get("ticket_id") not in (ticket_id, None):
            continue
        agent = e.get("agent", "")
        if agent not in AGENT_LABEL:
            continue

        row = rows.setdefault(agent, {
            "agent": AGENT_LABEL[agent],
            "tool_calls": 0,
            "tools_used": [],
            "delegated_to": [],
            "asked_by": [],
            "said": [],
            "tokens": 0,
        })
        row["tokens"] += (e.get("tokens_in") or 0) + (e.get("tokens_out") or 0)

        if e["event"] == "tool_call" and e.get("tool"):
            row["tool_calls"] += 1
            if e["tool"] not in row["tools_used"]:
                row["tools_used"].append(e["tool"])
        elif e["event"] == "delegation" and e.get("to_agent"):
            label = AGENT_LABEL.get(e["to_agent"], e["to_agent"])
            if label not in row["delegated_to"]:
                row["delegated_to"].append(label)
            target = rows.setdefault(e["to_agent"], {
                "agent": AGENT_LABEL.get(e["to_agent"], e["to_agent"]),
                "tool_calls": 0, "tools_used": [], "delegated_to": [],
                "asked_by": [], "said": [], "tokens": 0,
            })
            if AGENT_LABEL[agent] not in target["asked_by"]:
                target["asked_by"].append(AGENT_LABEL[agent])
        elif e["event"] == "agent_finished" and isinstance(e.get("result"), dict):
            summary = e["result"].get("summary")
            if summary:
                row["said"].append(summary)
        elif e["event"] == "ticket_finished" and isinstance(e.get("result"), dict):
            call = e["result"].get("decision")
            if call:
                row["said"].append(call)

    order = ["Boss", "Inventory", "Accounting", "Facilities", "CustomerService"]
    return [rows[a] for a in order if a in rows]


def main() -> int:
    log = json.loads((OUT / "run_log.json").read_text(encoding="utf-8"))
    trail = json.loads((OUT / "audit_trail.json").read_text(encoding="utf-8"))
    events = trail["events"]

    live_tickets = {t["id"]: t for t in get("/tickets")["tickets"]}
    approvals = get("/approvals?status=all")["approvals"]
    drafts = get("/drafts")["drafts"]
    closing_api = get("/cash")["balance"]
    closing_db = db_rows("SELECT balance FROM cash_accounts WHERE name='checking'")[0]["balance"]
    payments = db_rows("SELECT * FROM payments ORDER BY id")

    # --- the cash check: itemised movements must reconcile to the real balance ---
    opening = log["opening_balance"]
    itemised = round(sum(p["amount"] for p in payments), 2)
    expected_closing = round(opening - itemised, 2)
    assert closing_api == closing_db, f"API {closing_api} != DB {closing_db}"
    assert expected_closing == closing_db, (
        f"cash does not reconcile: {opening} - {itemised} = {expected_closing}, "
        f"but cash_accounts says {closing_db}"
    )

    tickets_out = []
    for entry in log["tickets"]:
        tid = entry["ticket_id"]
        run_ids = {p["run_id"] for p in entry["passes"]}
        live = live_tickets[tid]
        last_decision = entry["passes"][-1].get("decision") or {}
        ticket_payments = [p for p in payments
                           if any(a["ticket_id"] == tid and a["payment_id"] == p["id"]
                                  for a in approvals)]

        tickets_out.append({
            "id": tid,
            "subject": live["subject"],
            "requester": live["requester"],
            "final_status": live["status"],
            "outcome": last_decision.get("decision", ""),
            "reasoning": last_decision.get("reasoning", ""),
            "passes": len(entry["passes"]),
            "agent_contributions": contributions(events, run_ids, tid),
            "human_approvals": [
                {
                    "approval_id": a["approval_id"],
                    "kind": a["kind"],
                    "ref_id": a["ref_id"],
                    "amount": a["amount"],
                    "requested_by": a["requested_by"],
                    "reason": a["reason"],
                    "approved_by": a["approved_by"],
                    "result": a["message"],
                    "balance_before": a["balance_before"],
                    "balance_after": a["balance_after"],
                }
                for a in entry["approvals"]
            ],
            "payments_made": ticket_payments,
            "drafts_written": [
                {"id": d["id"], "kind": d["kind"], "audience": d["audience"],
                 "subject": d["subject"], "created_by": d["created_by"], "sent": False}
                for d in drafts if d["ticket_id"] == tid
            ],
            "cash": {
                "balance_before": entry["balance_before"],
                "balance_after": entry["balance_after"],
                "change": entry["cash_change"],
            },
        })

    report = {
        "assignment": "HW 5 — Campus Customs Multi-Agent Operations",
        "step": "Problem 9 — full board run, all three tickets resolved",
        "model": "gpt-6-luna",
        "human_approver": log["human"],
        "shop_date_today": db_rows("SELECT date_today FROM desk")[0]["date_today"],
        "started_utc": log["started_utc"],
        "finished_utc": log["finished_utc"],
        "cash": {
            "opening_balance_after_reset": opening,
            "total_paid_out": itemised,
            "closing_balance": closing_db,
            "reconciles": expected_closing == closing_db,
            "matches_cash_accounts_table": closing_api == closing_db,
            "note": "Cash only goes out — no revenue is modelled.",
        },
        "totals": {
            "tickets": len(tickets_out),
            "resolved": sum(1 for t in tickets_out if t["final_status"] != "open"),
            "payments_made": len(payments),
            "drafts_written": len(drafts),
            "drafts_sent": 0,
        },
        "tickets": tickets_out,
    }

    (OUT / "resolved_tickets.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )

    print(f"opening   ${opening:,.2f}")
    print(f"paid out  ${itemised:,.2f}")
    print(f"closing   ${closing_db:,.2f}  (cash_accounts agrees: {closing_api == closing_db})")
    print(f"resolved  {report['totals']['resolved']}/{report['totals']['tickets']}")
    print("written   output/resolved_tickets.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
