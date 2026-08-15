"""Agent 2 — shortlist candidates and maintain the contact pipeline + RTH view."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from config.schema import CANDIDATE_HEADERS, dict_to_row
from config.settings import settings
from core.sheets import SheetsClient
from graph.matching import build_contact_pipeline, contact_email, contact_phone
from graph.state import C_INTERESTED, C_QUEUED, E_OUTREACH, HiringState


def shortlist_candidates(event_id: str, req: dict[str, Any], educators: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return build_contact_pipeline(educators, req)


def persist_candidates(client: SheetsClient, event_id: str, matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc).isoformat()
    persisted: list[dict[str, Any]] = []
    for m in matches:
        row = {
            "event_id": event_id,
            "educator_email": contact_email(m),
            "educator_phone": contact_phone(m),
            "educator_name": m.get("name", m.get("educator_name", "")),
            "status": C_QUEUED,
            "followup_count": 0,
            "next_action_at": now,
            "calendly_link": "",
            "verdict": "",
            "round2_slot": "",
            "calendar_event_id": "",
            "created_at": now,
            "years_exp": m.get("years_exp", "?"),
        }
        client.append_row(settings.sheet_candidates, dict_to_row(CANDIDATE_HEADERS, row))
        persisted.append(row)
    return persisted


def rth_subset(candidates: list[dict[str, Any]]) -> list[str]:
    """RTH = interested-only subset (interested or advanced but not yet hired)."""
    active = {C_INTERESTED, "kyc_referred", "kyc_done", "accepted", "round2_scheduling", "round2_confirmed"}
    interested = [c for c in candidates if c.get("status") in active]
    return [c["educator_email"] for c in sorted(interested, key=lambda c: c.get("created_at", ""))]


def a2_shortlist_node(state: HiringState, client: SheetsClient, educators: list[dict[str, Any]]) -> dict[str, Any]:
    matches = shortlist_candidates(state["event_id"], state, educators)
    persisted = persist_candidates(client, state["event_id"], matches)
    return {
        "status": E_OUTREACH,
        "candidates": persisted,
        "rth_list": rth_subset(persisted),
        "audit": [f"shortlisted {len(persisted)} candidates"],
    }
