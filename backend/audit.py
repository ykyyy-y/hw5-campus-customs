"""Append-only audit trail for the Campus Customs agent team.

Every step of every agent loop lands in ``output/audit_trail.json``: the tool calls with
their arguments and results, the delegations between agents, the refusals, the token
cost, and the per-run summaries.

The file is **appended to, never overwritten**. A new run adds its events to the end of
the existing list, so the history of earlier runs survives. The on-disk shape is::

    {
      "file": "...",
      "events": [ {...}, {...} ],
      "runs":   [ {...} ]
    }

If the file is somehow corrupt, it is moved aside rather than deleted, so no history is
silently lost.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from models import AuditEvent, RunSummary

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"
TRAIL_PATH = OUTPUT_DIR / "audit_trail.json"

# Agent runs are concurrent inside one process; serialise the read-modify-write.
_LOCK = threading.Lock()
_SEQ: dict[str, int] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _empty() -> dict[str, Any]:
    return {
        "file": "Campus Customs agent audit trail — appended to on every run, never overwritten",
        "events": [],
        "runs": [],
    }


def _load() -> dict[str, Any]:
    if not TRAIL_PATH.exists():
        return _empty()
    try:
        data = json.loads(TRAIL_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        # Preserve whatever was there instead of clobbering it.
        TRAIL_PATH.rename(TRAIL_PATH.with_suffix(f".corrupt-{int(datetime.now().timestamp())}.json"))
        return _empty()
    data.setdefault("events", [])
    data.setdefault("runs", [])
    return data


def _save(data: dict[str, Any]) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    TRAIL_PATH.write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def _next_seq(run_id: str) -> int:
    _SEQ[run_id] = _SEQ.get(run_id, 0) + 1
    return _SEQ[run_id]


def log(
    run_id: str,
    event: str,
    agent: str,
    *,
    depth: int = 0,
    ticket_id: int | None = None,
    tool: str | None = None,
    arguments: dict[str, Any] | None = None,
    result: Any = None,
    to_agent: str | None = None,
    task: str | None = None,
    ok: bool = True,
    detail: str | None = None,
    duration_ms: float | None = None,
    model: str | None = None,
    tokens_in: int | None = None,
    tokens_out: int | None = None,
) -> AuditEvent:
    """Append one event to the trail and return it."""
    with _LOCK:
        record = AuditEvent(
            run_id=run_id,
            seq=_next_seq(run_id),
            at_utc=_now(),
            event=event,  # type: ignore[arg-type]
            agent=agent,
            depth=depth,
            ticket_id=ticket_id,
            tool=tool,
            arguments=arguments,
            result=result,
            to_agent=to_agent,
            task=task,
            ok=ok,
            detail=detail,
            duration_ms=round(duration_ms, 1) if duration_ms is not None else None,
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
        )
        data = _load()
        data["events"].append(record.model_dump())
        _save(data)
        return record


def log_run_summary(summary: RunSummary) -> None:
    """Append a finished run's summary alongside its events."""
    with _LOCK:
        data = _load()
        data["runs"].append(summary.model_dump())
        _save(data)


def read_trail() -> dict[str, Any]:
    """Return the whole trail, for the dashboard and for inspection."""
    with _LOCK:
        return _load()


def events_for_run(run_id: str) -> list[dict[str, Any]]:
    return [e for e in read_trail()["events"] if e.get("run_id") == run_id]
