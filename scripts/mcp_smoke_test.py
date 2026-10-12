"""Smoke-test every tool on the Campus Customs MCP server, end to end.

This does not import the tool functions directly. It reads `.mcp.json`, launches the
server exactly the way a client launches it (a subprocess speaking MCP over stdio),
performs the MCP handshake, lists the tools the server advertises, and calls each one.

Each tool's output is then cross-checked against a direct SQL read of
`data/campus_customs_new.db`, so the proof file shows not just what the tool said but
that it matches the database.

Writes `output/mcp_smoke.json`.

Run from the HW 5 folder::

    .venv/Scripts/python.exe scripts/mcp_smoke_test.py
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "campus_customs_new.db"
MCP_CONFIG = ROOT / ".mcp.json"
OUT_PATH = ROOT / "output" / "mcp_smoke.json"

# One test per tool, each tied to the open ticket it unlocks. "prompt" is what was typed
# at the vibe coder to drive the call.
TESTS = [
    {
        "ticket": 101,
        "prompt": (
            "Ticket 101 is Tauhid Zaman asking for a Classic Bulldog Tee in size S. "
            "Use the campus-customs MCP server to check stock for CC-TEE-WHITE size S "
            "for 1 unit, and tell me whether we can fill it and by how much we are short."
        ),
        "tool": "check_stock",
        "arguments": {"sku": "CC-TEE-WHITE", "size": "S", "qty_wanted": 1},
        "check_sql": (
            "SELECT name, qty AS on_hand, location FROM inventory "
            "WHERE sku = 'CC-TEE-WHITE' AND size = 'S'"
        ),
        "check_fields": {"name": "name", "on_hand": "on_hand", "location": "location"},
    },
    {
        "ticket": 102,
        "prompt": (
            "Ticket 102 is a rent notice from Elm City Properties on lease 1, and the "
            "email claims rent is due in 2 days. Use the campus-customs MCP server to get "
            "the rent due for lease 1 and confirm the amount and the due date against the "
            "shop's own date_today rather than the email."
        ),
        "tool": "get_rent_due",
        "arguments": {"lease_id": 1},
        "check_sql": (
            "SELECT space_name, landlord, monthly_rent, next_due FROM leases WHERE id = 1"
        ),
        "check_fields": {
            "space_name": "space_name",
            "landlord": "landlord",
            "monthly_rent": "monthly_rent",
            "next_due": "next_due",
        },
    },
    {
        "ticket": 103,
        "prompt": (
            "Ticket 103 is the Yale AI Club asking for a bulk discount on 20 CC-HOOD-NAVY "
            "hoodies in size M. Use the campus-customs MCP server to price 20 units and "
            "test a 20 percent discount at $46.40 per unit — I want the list margin, the "
            "cost floor, and whether that proposed price still clears cost."
        ),
        "tool": "price_quote",
        "arguments": {"sku": "CC-HOOD-NAVY", "qty": 20, "proposed_unit_price": 46.40},
        "check_sql": "SELECT unit_cost, list_price FROM pricing WHERE sku = 'CC-HOOD-NAVY'",
        "check_fields": {"unit_cost": "unit_cost", "list_price": "list_price"},
    },
]


def load_transport() -> StdioTransport:
    """Build the client transport from .mcp.json, so the test uses the real config."""
    config = json.loads(MCP_CONFIG.read_text(encoding="utf-8"))
    entry = config["mcpServers"]["campus-customs"]
    return StdioTransport(
        command=str(ROOT / entry["command"]),
        args=[str(ROOT / a) for a in entry["args"]],
        cwd=str(ROOT),
    )


def db_row(sql: str) -> dict:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(sql).fetchone()
        return dict(row) if row else {}
    finally:
        conn.close()


async def main() -> int:
    transport = load_transport()
    results = []

    async with Client(transport) as client:
        advertised = sorted(t.name for t in await client.list_tools())

        for test in TESTS:
            response = await client.call_tool(test["tool"], test["arguments"])
            output = response.data

            expected = db_row(test["check_sql"])
            mismatches = {}
            for out_field, db_field in test["check_fields"].items():
                if output.get(out_field) != expected.get(db_field):
                    mismatches[out_field] = {
                        "tool_said": output.get(out_field),
                        "database_says": expected.get(db_field),
                    }

            results.append(
                {
                    "ticket": test["ticket"],
                    "prompt": test["prompt"],
                    "tool": test["tool"],
                    "arguments": test["arguments"],
                    "output": output,
                    "verification": {
                        "sql": test["check_sql"],
                        "database_row": expected,
                        "matches_database": not mismatches,
                        "mismatches": mismatches,
                    },
                }
            )

    report = {
        "assignment": "HW 5 — Campus Customs Multi-Agent Operations",
        "step": "Problem 4 — MCP server connected and every tool smoke-tested",
        "server_name": "campus-customs",
        "mcp_config": str(MCP_CONFIG.relative_to(ROOT)).replace("\\", "/"),
        "transport": "stdio (server launched as a subprocess, real MCP handshake)",
        "database": "data/campus_customs_new.db",
        "shop_date_today": db_row("SELECT date_today FROM desk LIMIT 1")["date_today"],
        "run_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tools_advertised_by_server": advertised,
        "tools_tested": [r["tool"] for r in results],
        "all_tools_tested": advertised == sorted(r["tool"] for r in results),
        "all_outputs_match_database": all(
            r["verification"]["matches_database"] for r in results
        ),
        "tests": results,
    }

    OUT_PATH.parent.mkdir(exist_ok=True)
    OUT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(f"tools advertised : {advertised}")
    print(f"tools tested     : {report['tools_tested']}")
    print(f"all tools tested : {report['all_tools_tested']}")
    print(f"all match the db : {report['all_outputs_match_database']}")
    print(f"written          : output/mcp_smoke.json")
    return 0 if report["all_tools_tested"] and report["all_outputs_match_database"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
