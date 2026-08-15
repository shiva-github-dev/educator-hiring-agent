"""Tick scheduler — finds work 'due now' and advances A0 threads.

Resilience model (Milestone 1.5):
  * run_once never dies: any crash is captured to Log + errors.jsonl.
  * Per-event circuit breaker: N consecutive failures -> event status `error`,
    a Diagnosis job is queued for Agent 6.
  * Heartbeat: a `last_tick_at` health row is written every run.
  * Agent 6 queues are drained each tick (diagnosis + sandbox fix).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from config.schema import (
    read_health,
    read_new_requests,
    record_heartbeat,
    rows_with,
    set_health,
    set_run_state,
    update_request_row,
    update_row_by_index,
)
from config.settings import settings
from core.calendar import calendar_for_mode
from core.errors import capture_exception
from core.sheets import SheetsClient
from core.whatsapp_bridge import WhatsAppClient
from graph.agents.a3_comms import CommsAgent
from graph.agents.a6_support import enqueue_diagnosis, process_diagnosis_queue, process_sandbox_fixes
from graph.supervisor import default_supervisor, start_event
from scheduler.calendly import process_calendly
from scheduler.followups import process_follow_ups
from scheduler.inbound import process_inbound
from scheduler.round2 import confirm_round2, process_reminders, start_round2
from scheduler.verdicts import process_verdicts


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _reset_run_state(sheets: SheetsClient, event_id: str) -> None:
    set_run_state(sheets, event_id, failure_count=0, last_error="", last_error_ts="", status="ok", diagnosis_requested="no")


def _bump_failure(sheets: SheetsClient, event_id: str, exc: BaseException) -> bool:
    """Increment the event's failure count; returns True when the circuit breaker trips."""
    run_state = next((d for _, d in rows_with(sheets, settings.sheet_run_state, event_id=event_id)), {})
    count = int(run_state.get("failure_count", 0) or 0) + 1
    tripped = count >= settings.event_max_failures
    set_run_state(
        sheets,
        event_id,
        failure_count=count,
        last_error=f"{type(exc).__name__}: {exc}"[:500],
        last_error_ts=_now(),
        status="error" if tripped else "retrying",
        diagnosis_requested="yes" if tripped else "no",
    )
    if tripped:
        try:
            enqueue_diagnosis(sheets, event_id, type(exc).__name__, str(exc))
        except Exception:  # noqa: BLE001
            pass
    return tripped


def sync_candidates(sheets: SheetsClient, result: dict[str, Any]) -> int:
    """Write graph-state candidate statuses back to the Candidates sheet
    (the sheet is the source of truth for the follow-up/inbound workers)."""
    event_id = result.get("event_id", "")
    if not event_id:
        return 0
    by_email = {c["educator_email"]: c for c in result.get("candidates", [])}
    updated = 0
    for idx, data in rows_with(sheets, settings.sheet_candidates, event_id=event_id):
        state_cand = by_email.get(data.get("educator_email", ""))
        if not state_cand:
            continue
        changed = dict(data)
        for key in ("status", "followup_count", "next_action_at", "calendly_link", "verdict", "round2_slot", "calendar_event_id"):
            if key in state_cand and state_cand.get(key) is not None:
                changed[key] = state_cand[key]
        changed["updated_at"] = _now()
        update_row_by_index(sheets, settings.sheet_candidates, idx, changed)
        updated += 1
    return updated


def process_new_requests(sheets: SheetsClient, graph: Any) -> int:
    started = 0
    for row_index, data in read_new_requests(sheets):
        event_id = data.get("event_id") or uuid.uuid4().hex[:12]
        data["event_id"] = event_id
        try:
            req: dict[str, Any] = {
                "event_id": event_id,
                "centre": data.get("centre", ""),
                "location": data.get("location", ""),
                "subject": data.get("subject", ""),
                "exam": data.get("exam", ""),
                "min_experience": data.get("min_experience", 0),
                "hiring_type": data.get("hiring_type", "fresh"),
                "leaving_educator": data.get("leaving_educator", ""),
                "round2_educator_email": data.get("round2_educator_email", ""),
                "round2_educator_phone": data.get("round2_educator_phone", ""),
            }
            result = start_event(graph, req)
            data["status"] = result.get("status", "matching")
            data["updated_at"] = _now()
            update_request_row(sheets, row_index, data)
            sync_candidates(sheets, result)
            _reset_run_state(sheets, event_id)
            started += 1
        except Exception as exc:  # noqa: BLE001
            capture_exception(exc, source="tick", event_id=event_id, node="start_event", sheets=sheets)
            if _bump_failure(sheets, event_id, exc):
                data["status"] = "error"
                data["updated_at"] = _now()
                update_request_row(sheets, row_index, data)
    return started


def verify_tick(graph: Any) -> int:
    """Resume evaluating threads to check verdicts. Milestone 4+ wires this."""
    return 0


def process_inbound_messages(sheets: SheetsClient) -> int:
    wa = WhatsAppClient()
    if not wa.is_ready():
        return 0
    comms = CommsAgent(sheets=sheets)
    last_poll = int(read_health(sheets).get("last_inbox_poll", 0) or 0)
    processed, new_poll = process_inbound(sheets, comms, wa, last_poll)
    if new_poll:
        set_health(sheets, "last_inbox_poll", str(new_poll))
    if processed:
        sheets.log(f"inbound processed {processed} reply/replies")
    return processed


def run_once() -> None:
    sheets: SheetsClient | None = None
    try:
        sheets = SheetsClient()
        graph = default_supervisor(sheets=sheets)
        record_heartbeat(sheets, "last_tick_at")
        sheets.log("tick run started")
        process_new_requests(sheets, graph)
        verify_tick(graph)
        process_inbound_messages(sheets)
        process_follow_ups(sheets, CommsAgent(sheets=sheets))
        process_calendly(sheets, CommsAgent(sheets=sheets))
        process_verdicts(sheets, CommsAgent(sheets=sheets))
        start_round2(sheets, CommsAgent(sheets=sheets))
        calendar = calendar_for_mode()
        confirm_round2(sheets, CommsAgent(sheets=sheets), calendar)
        process_reminders(sheets, CommsAgent(sheets=sheets))
        process_diagnosis_queue(sheets)
        process_sandbox_fixes(sheets)
        record_heartbeat(sheets, "last_tick_at")
        sheets.log("tick run finished")
    except Exception as exc:  # noqa: BLE001
        capture_exception(exc, source="tick", node="run_once", sheets=sheets)