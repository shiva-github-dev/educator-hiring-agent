"""Alternate-day follow-up cadence for quiet candidates.

Drives the Candidates sheet: a contacted candidate with no reply gets a
follow-up every `follow_up_interval_hours` up to `follow_up_max` times, then
is dropped (no_response). All messages go through Agent 3 (Comms).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from config.schema import row_to_dict, rows_with, update_row_by_index
from config.settings import settings
from core.sheets import SheetsClient
from graph.agents.a3_comms import CommsAgent
from graph.state import C_NO_RESPONSE
from graph.tools.scheduling import is_due, next_follow_up_at

FOLLOWABLE = {"contacted", "follow_up_1", "follow_up_2", "follow_up_3"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_request(sheets: SheetsClient, event_id: str) -> dict[str, Any]:
    rows = rows_with(sheets, settings.sheet_centre_requests, event_id=event_id)
    return rows[0][1] if rows else {}


def process_follow_ups(sheets: SheetsClient, comms: CommsAgent) -> tuple[int, int]:
    """Returns (follow_ups_sent, dropped)."""
    rows = sheets.read_range(settings.sheet_candidates)
    if not rows:
        return 0, 0
    headers = [str(h).strip() for h in rows[0]]
    now = datetime.now(timezone.utc)
    sent = dropped = 0
    for i, row in enumerate(rows[1:], start=2):
        cand = row_to_dict(headers, row)
        status = cand.get("status", "")
        if status not in FOLLOWABLE:
            continue
        if not is_due(cand.get("next_action_at"), now):
            continue
        event_id = cand.get("event_id", "")
        count = int(cand.get("followup_count", 0) or 0)

        if count >= settings.follow_up_max:
            cand["status"] = C_NO_RESPONSE
            cand["updated_at"] = _now()
            update_row_by_index(sheets, settings.sheet_candidates, i, cand)
            sheets.log(f"dropped {cand.get('educator_email')}: no reply after follow-ups", event_id, cand.get("educator_email"))
            dropped += 1
            continue

        req = get_request(sheets, event_id)
        context = cand | {"subject": req.get("subject", ""), "location": req.get("location", ""), "event_id": event_id}
        ok = comms.send_follow_up(context, cand)
        if ok:
            count += 1
            cand["followup_count"] = count
            cand["status"] = f"follow_up_{count}"
            cand["next_action_at"] = next_follow_up_at(_now())
            cand["updated_at"] = _now()
            update_row_by_index(sheets, settings.sheet_candidates, i, cand)
            sheets.log(f"follow-up {count} sent to {cand.get('educator_email')}", event_id, cand.get("educator_email"))
            sent += 1
    return sent, dropped