"""A0 scheduling utilities: Calendly links, slot negotiation, reminders.

Round-2 (and the AI knowledge-check) scheduling logic lives here as tools
invoked by A0; all messaging is executed through Agent 3. Interfaces are
defined now; concrete vendor calls land in later milestones.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from config.settings import settings


def build_calendly_link(candidate_email: str) -> str:
    # `email` pre-fills the booking form; the checker platform maps the
    # attendee email back to its verdict sheet.
    from urllib.parse import urlencode

    query = urlencode({"email": candidate_email})
    return f"{settings.calendly_base}?{query}"


def compute_reminder_at(slot_start_iso: str, minutes_before: int = 10) -> str:
    start = datetime.fromisoformat(slot_start_iso)
    return (start - timedelta(minutes=minutes_before)).isoformat()


def propose_slots_to_candidate(slots: list[str]) -> str:
    """Human-readable prompt listing educator-provided slots for the candidate."""
    lines = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(slots))
    return f"Available slots for your interview:\n{lines}\nPlease reply with the number that works for you."


def negotiate_slot(centre_slots: list[str], candidate_choice: str | None) -> str | None:
    """Resolve a common slot. Returns the chosen ISO slot or None to re-ask."""
    if not candidate_choice:
        return None
    try:
        idx = int(candidate_choice.strip())
        if 1 <= idx <= len(centre_slots):
            return centre_slots[idx - 1]
    except ValueError:
        pass
    return None


def is_due(action_at: str | None, now: datetime | None = None) -> bool:
    if not action_at:
        return False
    now = now or datetime.now(timezone.utc)
    try:
        dt = datetime.fromisoformat(str(action_at))
    except ValueError:
        return False
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt <= now


def next_follow_up_at(current: str | None) -> str:
    base = datetime.fromisoformat(current) if current else datetime.now(timezone.utc)
    return (base + timedelta(hours=settings.follow_up_interval_hours)).isoformat()
