"""Dump repro context for a failing event — everything a coding agent needs.

Usage:
    python -m tools.diagnose --event <event_id>
    python -m tools.diagnose --event <event_id> --json
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone

from config.schema import rows_with
from config.settings import settings
from core.errors import load_error_records
from core.sheets import SheetsClient
from graph.supervisor import DB_PATH


def read_thread_state(thread_id: str) -> dict:
    """Last checkpoint channel values for a thread, or {} when none exists."""
    if not DB_PATH.exists():
        return {}
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver

        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        saver = SqliteSaver(conn)
        tup = saver.get_tuple({"configurable": {"thread_id": thread_id}})
        conn.close()
        if tup is None:
            return {}
        checkpoint = getattr(tup, "checkpoint", None) or {}
        return checkpoint.get("channel_values", {}) or {}
    except Exception as exc:  # noqa: BLE001
        return {"_read_error": str(exc)}


def collect(event_id: str) -> dict:
    sheets = SheetsClient()
    error_records = load_error_records(event_id=event_id)
    run_state = [d for _, d in rows_with(sheets, settings.sheet_run_state, event_id=event_id)]
    diagnosis = [d for _, d in rows_with(sheets, settings.sheet_diagnosis, event_id=event_id)]
    log_rows = [d for _, d in rows_with(sheets, settings.sheet_log, event_id=event_id)]
    candidates = [d for _, d in rows_with(sheets, settings.sheet_candidates, event_id=event_id)]
    request_rows = [d for _, d in rows_with(sheets, settings.sheet_centre_requests, event_id=event_id)]
    return {
        "event_id": event_id,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "request": request_rows[-1] if request_rows else {},
        "run_state": run_state[-1] if run_state else {},
        "thread_state": read_thread_state(event_id),
        "candidates": candidates,
        "diagnosis": diagnosis[-1] if diagnosis else {},
        "error_records": error_records,
        "log_rows": log_rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Dump repro context for a failing event.")
    parser.add_argument("--event", required=True, help="event_id / thread_id")
    parser.add_argument("--json", action="store_true", help="emit JSON")
    args = parser.parse_args()

    data = collect(args.event)
    if args.json:
        print(json.dumps(data, indent=2, default=str))
        return 0

    d = data
    print(f"Event: {d['event_id']}  (collected {d['collected_at']})")
    print("\n-- RUN STATE --")
    print(json.dumps(d["run_state"], indent=2, default=str))
    print("\n-- REQUEST --")
    print(json.dumps(d["request"], indent=2, default=str))
    print("\n-- THREAD STATE (last checkpoint) --")
    ts = d["thread_state"]
    print(json.dumps({
        k: v for k, v in ts.items()
        if k in {"event_id", "status", "candidates", "rth_list"}
    }, indent=2, default=str) if ts else "(no checkpoint yet)")
    print(f"\n-- CANDIDATES ({len(d['candidates'])}) --")
    for c in d["candidates"][-10:]:
        print(f"  {c.get('educator_email')} status={c.get('status')} verdict={c.get('verdict')}")
    print(f"\n-- DIAGNOSIS --")
    print(json.dumps(d["diagnosis"], indent=2, default=str))
    print(f"\n-- ERROR RECORDS ({len(d['error_records'])}) --")
    for e in d["error_records"]:
        print(f"  [{e.get('ts')}] {e.get('source')}::{e.get('node')} {e.get('exc_type')}: {e.get('message')}")
    print(f"\n-- LOG ROWS ({len(d['log_rows'])}) --")
    for row in d["log_rows"][-20:]:
        print("  " + " | ".join(str(row.get(h, "")) for h in ["ts", "level", "candidate_email", "message"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())