"""Inbound WhatsApp handling — match a reply to a candidate and advance it.

Agent 3 owns all comms; inbound replies arrive via the sidecar's inbox and
are processed here on each tick. Reply classification is keyword-first with
an optional LLM fallback.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from config.schema import CANDIDATE_HEADERS, dict_to_row, row_to_dict, update_row_by_index
from config.settings import settings
from core.sheets import SheetsClient
from core.whatsapp_bridge import WhatsAppClient
from graph.agents.a3_comms import CommsAgent, classify_reply
from graph.state import C_DECLINED, C_INTERESTED
from scheduler.round2 import process_round2_inbound

ACTIVE_OUTREACH = {"contacted", "follow_up_1", "follow_up_2", "follow_up_3", C_INTERESTED}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_phone(value: str) -> str:
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    return digits[-10:]


def find_candidates_by_phone(sheets: SheetsClient, from_number: str) -> list[tuple[int, dict[str, Any]]]:
    rows = sheets.read_range(settings.sheet_candidates)
    if not rows:
        return []
    headers = [str(h).strip() for h in rows[0]]
    target = normalize_phone(from_number)
    matches: list[tuple[int, dict[str, Any]]] = []
    for i, row in enumerate(rows[1:], start=2):
        data = row_to_dict(headers, row)
        if normalize_phone(data.get("educator_phone", "")) == target:
            matches.append((i, data))
    return matches


def handle_message(sheets: SheetsClient, comms: CommsAgent, from_number: str, body: str) -> bool:
    """Process one inbound message; returns True if it was consumed by the agent."""
    # Round-2 slot negotiation replies (educator/candidate) take precedence.
    if process_round2_inbound(sheets, comms, from_number, body):
        return True
    matches = find_candidates_by_phone(sheets, from_number)
    if not matches:
        return False
    label = classify_reply(body)
    for row_index, cand in matches:
        if cand.get("status") not in ACTIVE_OUTREACH:
            continue
        if label == "yes":
            cand["status"] = C_INTERESTED
            comms.send_interested_ack(cand)
        elif label == "no":
            cand["status"] = C_DECLINED
        else:
            continue  # unclear — leave for the follow-up cadence
        cand["updated_at"] = _now()
        update_row_by_index(sheets, settings.sheet_candidates, row_index, cand)
        sheets.log(
            f"candidate {cand.get('educator_email')} replied '{label}'",
            cand.get("event_id", ""),
            cand.get("educator_email", ""),
        )
        return True
    return False


def simulate_inbound(sheets: SheetsClient, comms: CommsAgent, from_number: str, body: str) -> bool:
    """Demo-mode entry point: feed a message into the real pipeline (no sidecar)."""
    return handle_message(sheets, comms, from_number, body)


def process_inbound(
    sheets: SheetsClient,
    comms: CommsAgent,
    wa: WhatsAppClient,
    last_poll: int = 0,
) -> tuple[int, int]:
    """Poll the sidecar inbox and advance matching candidates. Returns (processed, new_last_poll)."""
    try:
        messages = wa.inbox(after=last_poll)
    except Exception as exc:  # noqa: BLE001
        sheets.log(f"inbound poll failed: {exc}")
        return 0, last_poll

    if not messages:
        return 0, last_poll

    new_last_poll = max(m["when"] for m in messages)
    processed = 0
    for msg in messages:
        if handle_message(sheets, comms, str(msg.get("from", "")), str(msg.get("body", ""))):
            processed += 1
    return processed, new_last_poll