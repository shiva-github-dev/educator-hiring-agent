from datetime import datetime, timedelta, timezone

from graph.tools.scheduling import (
    build_calendly_link,
    compute_reminder_at,
    is_due,
    negotiate_slot,
    next_follow_up_at,
)


def test_calendly_link_embeds_email():
    link = build_calendly_link("cand@x.com")
    assert "cand%40x.com" in link or "cand@x.com" in link
    assert "calendly.com" in link


def test_reminder_computation():
    assert compute_reminder_at("2026-08-15T10:00:00+00:00") == "2026-08-15T09:50:00+00:00"


def test_is_due():
    now = datetime.now(timezone.utc)
    assert is_due((now - timedelta(minutes=1)).isoformat(), now)
    assert not is_due((now + timedelta(days=1)).isoformat(), now)
    assert not is_due(None, now)
    assert not is_due("not-a-date", now)


def test_negotiate_slot():
    slots = ["2026-08-16T09:00:00+05:30", "2026-08-16T11:00:00+05:30"]
    assert negotiate_slot(slots, "2") == slots[1]
    assert negotiate_slot(slots, "0") is None
    assert negotiate_slot(slots, "abc") is None
    assert negotiate_slot(slots, None) is None


def test_next_follow_up():
    now = datetime.now(timezone.utc)
    nxt = datetime.fromisoformat(next_follow_up_at(now.isoformat()))
    assert nxt > now


def test_slot_end_preserves_timezone():
    from core.calendar import slot_end

    assert slot_end("2026-08-20T11:00:00+00:00", 60) == "2026-08-20T12:00:00+00:00"
    assert slot_end("2026-08-20T11:00:00+05:30", 60) == "2026-08-20T12:00:00+05:30"