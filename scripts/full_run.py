"""Drive a complete board run through the backend's own HTTP routes.

Nothing here bypasses the system under test. The database is reset through `POST /reset`,
tickets are handed to the agents through `POST /tickets/{id}/run`, and every payment is
authorised through `POST /approvals/{id}/decide` — the same route the Approve button on the
React desk calls, acting as the named human.

The loop per ticket is deliberately the realistic one:

1. Hand the ticket to the team. The agents analyse it and queue any payment it needs.
   They cannot pay; nothing moves.
2. The human approves the queued payment. Cash moves here and only here.
3. Hand the ticket back to the team. Now the blocker is gone, so the Boss can finish the
   work and close the ticket.

Writes `output/run_log.json` with the cash position at every step, which is what the Cash
tab and `resolved_tickets.json` are built from.

Run (with the backend already up on port 8000)::

    .venv/Scripts/python.exe scripts/full_run.py
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

API = "http://localhost:8000"
ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = ROOT / "output" / "run_log.json"

HUMAN = "Yookyung Eom"
TICKETS = [101, 102, 103]

#: How long to let one ticket run before giving up on it.
RUN_TIMEOUT_S = 1500


def call(path: str, method: str = "GET", body: dict | None = None) -> Any:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{API}{path}", data=data, method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"__error__": e.code, "detail": json.loads(e.read() or b"{}").get("detail")}


def balance() -> float:
    return call("/cash")["balance"]


def wait_for_run(run_id: str) -> dict:
    """Poll until the agents finish this ticket."""
    deadline = time.time() + RUN_TIMEOUT_S
    while time.time() < deadline:
        page = call(f"/events?run_id={run_id}&limit=1")
        state = page.get("run")
        if state and state["status"] != "running":
            return state
        time.sleep(4)
    raise TimeoutError(f"{run_id} did not finish within {RUN_TIMEOUT_S}s")


def hand_to_team(ticket_id: int, pass_no: int, attempts: int = 3) -> dict:
    """Run one pass, retrying when the model gateway fails transiently.

    Portkey occasionally returns a 500 or times out mid-run. That is an infrastructure
    failure, not a decision, so it is retried rather than recorded as the ticket's outcome.
    """
    for attempt in range(1, attempts + 1):
        started = call(f"/tickets/{ticket_id}/run", "POST")
        if "__error__" in started:
            raise RuntimeError(f"could not start ticket {ticket_id}: {started}")
        label = f"  pass {pass_no}" + (f" (attempt {attempt})" if attempt > 1 else "")
        print(f"{label}: handed ticket {ticket_id} to the team ({started['run_id']})", flush=True)

        state = wait_for_run(started["run_id"])
        if state["status"] == "error":
            print(f"{label}: model gateway failed — {state['error'][:90]}", flush=True)
            if attempt < attempts:
                time.sleep(20)
                continue
            return state

        decision = state.get("decision") or {}
        print(f"{label}: resolved={decision.get('resolved')} "
              f"consulted={decision.get('agents_consulted')}", flush=True)
        return state
    return state


def approve_pending(ticket_id: int) -> list[dict]:
    """Authorise every payment the agents queued for this ticket. Cash moves here."""
    queue = call("/approvals?status=pending")["approvals"]
    mine = [a for a in queue if a["ticket_id"] == ticket_id]
    settled = []
    for a in mine:
        before = balance()
        result = call(f"/approvals/{a['id']}/decide", "POST",
                      {"decision": "approve", "decided_by": HUMAN})
        after = result.get("balance_after", before)
        print(f"  human approved #{a['id']} {a['kind']} {a['ref_id']} "
              f"${a['amount']:,.2f} -> balance ${before:,.2f} to ${after:,.2f}", flush=True)
        settled.append({
            "approval_id": a["id"], "kind": a["kind"], "ref_id": a["ref_id"],
            "amount": a["amount"], "reason": a["reason"], "requested_by": a["requested_by"],
            "approved_by": HUMAN, "ok": result.get("ok"),
            "message": result.get("message"),
            "balance_before": before, "balance_after": after,
        })
    if not mine:
        print("  nothing queued for a human on this ticket", flush=True)
    return settled


def main() -> int:
    print("=== resetting the shop ===", flush=True)
    reset = call("/reset", "POST")
    opening = reset["balance"]
    print(f"  opening checking balance: ${opening:,.2f}", flush=True)
    print(f"  open tickets: {reset['open_tickets']}", flush=True)

    log: dict[str, Any] = {
        "started_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "human": HUMAN,
        "opening_balance": opening,
        "tickets": [],
    }

    for ticket_id in TICKETS:
        print(f"\n=== ticket {ticket_id} ===", flush=True)
        before = balance()
        entry: dict[str, Any] = {
            "ticket_id": ticket_id,
            "balance_before": before,
            "passes": [],
            "approvals": [],
        }

        first = hand_to_team(ticket_id, 1)
        entry["passes"].append({"pass": 1, "run_id": first["run_id"],
                                "decision": first.get("decision")})

        entry["approvals"] = approve_pending(ticket_id)

        # Hand the ticket back while it is still open: either a payment had to clear first,
        # or the Boss left work unfinished. Capped so a ticket that genuinely cannot close
        # does not loop forever.
        for pass_no in (2, 3):
            status = next(t["status"] for t in call("/tickets")["tickets"] if t["id"] == ticket_id)
            if status != "open":
                break
            nxt = hand_to_team(ticket_id, pass_no)
            entry["passes"].append({"pass": pass_no, "run_id": nxt["run_id"],
                                    "decision": nxt.get("decision")})
            entry["approvals"] += approve_pending(ticket_id)

        after = balance()
        entry["balance_after"] = after
        entry["cash_change"] = round(after - before, 2)
        entry["final_status"] = call("/tickets")["tickets"]
        entry["final_status"] = next(
            t["status"] for t in entry["final_status"] if t["id"] == ticket_id
        )
        print(f"  ticket {ticket_id}: {entry['final_status']} | "
              f"cash ${before:,.2f} -> ${after:,.2f} ({entry['cash_change']:+,.2f})", flush=True)
        log["tickets"].append(entry)

    closing = balance()
    log["closing_balance"] = closing
    log["total_spent"] = round(opening - closing, 2)
    log["finished_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    log["final_tickets"] = call("/tickets")["tickets"]
    log["payments"] = call("/approvals?status=all")["approvals"]
    log["drafts"] = call("/drafts")["drafts"]

    LOG_PATH.write_text(json.dumps(log, indent=2) + "\n", encoding="utf-8")

    print("\n=== board complete ===", flush=True)
    print(f"  opening ${opening:,.2f} -> closing ${closing:,.2f} "
          f"(spent ${log['total_spent']:,.2f})", flush=True)
    for t in log["final_tickets"]:
        print(f"  ticket {t['id']}: {t['status']}", flush=True)
    print(f"  written: output/run_log.json", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
