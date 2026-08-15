from datetime import datetime, timedelta, timezone

from config.schema import CANDIDATE_HEADERS, CENTRE_REQUEST_HEADERS, dict_to_row
from graph.state import C_CONTACTED, C_NO_RESPONSE
from scheduler.followups import process_follow_ups
from tests.helpers import MemorySheets, RecordingComms

PHONE = "919876543210"
NOW = datetime.now(timezone.utc)


def _candidate(event="e1", status=C_CONTACTED, count=0, next_at=None):
    return {
        "event_id": event, "educator_email": "a@x.com", "educator_phone": PHONE,
        "educator_name": "A", "status": status, "followup_count": count,
        "next_action_at": next_at or (NOW - timedelta(hours=1)).isoformat(),
        "calendly_link": "", "verdict": "", "round2_slot": "",
        "calendar_event_id": "", "created_at": "2026-08-01T00:00:00+00:00",
    }


def _setup(rows: list[dict]):
    sheets = MemorySheets()
    sheets.seed("Candidates", CANDIDATE_HEADERS, [dict_to_row(CANDIDATE_HEADERS, r) for r in rows])
    sheets.seed("CentreRequests", CENTRE_REQUEST_HEADERS, [dict_to_row(CENTRE_REQUEST_HEADERS, {
        "event_id": "e1", "centre": "C", "location": "Pune", "subject": "Physics",
        "exam": "JEE", "min_experience": 2, "hiring_type": "fresh", "leaving_educator": "",
        "round2_educator_email": "", "round2_educator_phone": "", "status": "new",
        "created_at": "", "updated_at": "",
    })])
    sheets.seed("Log", ["message", "event_id", "candidate_email"], [])
    return sheets


def test_follow_up_sent_and_advanced():
    sheets = _setup([_candidate()])
    comms = RecordingComms()
    sent, dropped = process_follow_ups(sheets, comms)
    assert sent == 1 and dropped == 0
    cand = sheets.read_all("Candidates")[0]
    assert cand["status"] == "follow_up_1"
    assert int(cand["followup_count"]) == 1
    assert datetime.fromisoformat(cand["next_action_at"]) > NOW
    assert any(m == "follow_up" for m, _ in comms.calls)


def test_drop_after_max_followups():
    sheets = _setup([_candidate(count=3, status="follow_up_3")])
    sent, dropped = process_follow_ups(sheets, RecordingComms())
    assert sent == 0 and dropped == 1
    assert sheets.read_all("Candidates")[0]["status"] == C_NO_RESPONSE


def test_not_due_candidate_untouched():
    future = (NOW + timedelta(hours=24)).isoformat()
    sheets = _setup([_candidate(next_at=future)])
    sent, dropped = process_follow_ups(sheets, RecordingComms())
    assert sent == 0 and dropped == 0
    assert sheets.read_all("Candidates")[0]["status"] == C_CONTACTED