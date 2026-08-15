import json

from config.schema import (
    CANDIDATE_HEADERS,
    CENTRE_REQUEST_HEADERS,
    ROUND2_HEADERS,
    dict_to_row,
)
from graph.state import C_ACCEPTED
from scheduler.round2 import (
    confirm_round2,
    parse_slots,
    process_reminders,
    process_round2_inbound,
    start_round2,
)
from tests.helpers import MemorySheets, RecordingComms

CAND_PHONE = "919876543210"
EDU_PHONE = "919900001111"


class FakeCalendar:
    def __init__(self, fail=False):
        self.fail_slots: list[str] = []

    def create_event(self, summary, slot, attendees, description=""):
        return "cal-1"


def _candidate():
    return {
        "event_id": "e1", "educator_email": "a@x.com", "educator_phone": CAND_PHONE,
        "educator_name": "A", "status": C_ACCEPTED, "followup_count": 0,
        "next_action_at": "", "calendly_link": "https://calendly.com/x/1", "verdict": "pass",
        "round2_slot": "", "calendar_event_id": "", "created_at": "2026-08-01T00:00:00+00:00",
    }


def _request():
    return {
        "event_id": "e1", "centre": "C", "location": "Pune", "subject": "Physics",
        "exam": "JEE", "min_experience": 2, "hiring_type": "fresh", "leaving_educator": "",
        "round2_educator_email": "r@x.com", "round2_educator_phone": EDU_PHONE,
        "status": "new", "created_at": "", "updated_at": "",
    }


def _sheets(state="", slots="[]", choice="", alt="", reminder_at=""):
    sheets = MemorySheets()
    sheets.seed("Candidates", CANDIDATE_HEADERS, [dict_to_row(CANDIDATE_HEADERS, _candidate())])
    sheets.seed("CentreRequests", CENTRE_REQUEST_HEADERS, [dict_to_row(CENTRE_REQUEST_HEADERS, _request())])
    if state:
        sheets.seed("Round2", ROUND2_HEADERS, [dict_to_row(ROUND2_HEADERS, {
            "event_id": "e1", "candidate_email": "a@x.com", "state": state,
            "slots_json": slots, "choice": choice, "alt_text": alt,
            "scheduled_at": "", "calendar_event_id": "", "reminder_at": reminder_at,
            "reminded_at": "", "created_at": "", "updated_at": "",
        })])
    else:
        sheets.seed("Round2", ROUND2_HEADERS, [])
    sheets.seed("Log", ["message", "event_id", "candidate_email"], [])
    return sheets


def test_parse_slots():
    assert parse_slots("- 2026-08-20T11:00:00\n* 2026-08-21T17:30:00") == [
        "2026-08-20T11:00:00", "2026-08-21T17:30:00",
    ]


def test_start_round2_requests_slots():
    sheets = _sheets()
    comms = RecordingComms()
    assert start_round2(sheets, comms) == 1
    row = sheets.read_all("Round2")[0]
    assert row["state"] == "awaiting_educator_slots"
    assert any(c[0] == "whatsapp" and c[1]["to"] == EDU_PHONE for c in comms.calls)


def test_educator_slots_proposed_to_candidate():
    sheets = _sheets(state="awaiting_educator_slots")
    comms = RecordingComms()
    ok = process_round2_inbound(sheets, comms, EDU_PHONE, "2026-08-20T11:00:00\n2026-08-21T17:30:00")
    assert ok
    row = sheets.read_all("Round2")[0]
    assert row["state"] == "awaiting_candidate_choice"
    assert json.loads(row["slots_json"]) == ["2026-08-20T11:00:00", "2026-08-21T17:30:00"]
    assert any(c[0] == "whatsapp" and c[1]["to"] == "9876543210" for c in comms.calls)  # normalized candidate number


def test_candidate_picks_slot():
    sheets = _sheets(state="awaiting_candidate_choice", slots='["2026-08-20T11:00:00","2026-08-21T17:30:00"]')
    ok = process_round2_inbound(sheets, RecordingComms(), CAND_PHONE, "2")
    assert ok
    row = sheets.read_all("Round2")[0]
    assert row["state"] == "candidate_chosen"
    assert row["choice"] == "2026-08-21T17:30:00"


def test_candidate_prefers_alt():
    sheets = _sheets(state="awaiting_candidate_choice", slots='["2026-08-20T11:00:00"]')
    comms = RecordingComms()
    ok = process_round2_inbound(sheets, comms, CAND_PHONE, "not good, other time")
    assert ok
    row = sheets.read_all("Round2")[0]
    assert row["state"] == "awaiting_candidate_alt"
    assert row["alt_text"] == "not good, other time"
    assert any(c[0] == "whatsapp" and c[1]["to"] == "9900001111" for c in comms.calls)  # normalized educator number


def test_educator_confirms_alt():
    sheets = _sheets(state="awaiting_candidate_alt", alt="not good")
    ok = process_round2_inbound(sheets, RecordingComms(), EDU_PHONE, "yes that works")
    assert ok
    row = sheets.read_all("Round2")[0]
    assert row["state"] == "candidate_chosen"
    assert row["choice"] == "yes that works"


def test_confirm_creates_event_and_notifies():
    sheets = _sheets(state="candidate_chosen", choice="2026-08-20T11:00:00+00:00")
    comms = RecordingComms()
    assert confirm_round2(sheets, comms, FakeCalendar()) == 1
    row = sheets.read_all("Round2")[0]
    assert row["state"] == "confirmed"
    assert row["calendar_event_id"] == "cal-1"
    assert row["reminder_at"]
    targets = {c[1]["to"] for c in comms.calls if c[0] == "whatsapp"}
    assert {CAND_PHONE, EDU_PHONE} <= targets


def test_confirm_unparseable_errors():
    sheets = _sheets(state="candidate_chosen", choice="next tuesday")
    assert confirm_round2(sheets, RecordingComms(), FakeCalendar()) == 0
    row = sheets.read_all("Round2")[0]
    assert row["state"] == "confirm_error"


def test_reminders_sent_once():
    sheets = _sheets(state="confirmed", reminder_at="2020-01-01T00:00:00+00:00")
    comms = RecordingComms()
    assert process_reminders(sheets, comms) == 1
    row = sheets.read_all("Round2")[0]
    assert row["state"] == "done"
    assert row["reminded_at"]
    assert process_reminders(sheets, comms) == 0
    n = sum(1 for m, _ in comms.calls if m == "whatsapp" and "Reminder" in _["text"])
    assert n == 2