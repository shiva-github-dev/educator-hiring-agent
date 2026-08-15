from config.schema import CANDIDATE_HEADERS, dict_to_row
from graph.state import C_CONTACTED, C_DECLINED, C_INTERESTED
from scheduler.inbound import normalize_phone, process_inbound
from tests.helpers import FakeWa, MemorySheets, RecordingComms


def _candidate(**overrides):
    base = {
        "event_id": "e1", "educator_email": "a@x.com", "educator_phone": "919876543210",
        "educator_name": "A", "status": C_CONTACTED, "followup_count": 0,
        "next_action_at": "", "calendly_link": "", "verdict": "", "round2_slot": "",
        "calendar_event_id": "", "created_at": "2026-08-01T00:00:00+00:00",
    }
    base.update(overrides)
    return base


def _sheets(candidate: dict) -> MemorySheets:
    sheets = MemorySheets()
    sheets.seed("Candidates", CANDIDATE_HEADERS, [dict_to_row(CANDIDATE_HEADERS, candidate)])
    sheets.seed("Log", ["message", "event_id", "candidate_email"], [])
    return sheets


def test_normalize_phone():
    assert normalize_phone("+91 98765 43210") == "9876543210"
    assert normalize_phone("919876543210") == "9876543210"


def test_yes_reply_marks_interested():
    sheets = _sheets(_candidate())
    wa = FakeWa([{"from": "919876543210", "body": "yes", "when": 1000}])
    comms = RecordingComms()
    processed, new_poll = process_inbound(sheets, comms, wa, last_poll=0)
    assert processed == 1
    assert new_poll == 1000
    cand = sheets.read_all("Candidates")[0]
    assert cand["status"] == C_INTERESTED
    assert any(m == "interested_ack" for m, _ in comms.calls)


def test_no_reply_marks_declined():
    sheets = _sheets(_candidate())
    wa = FakeWa([{"from": "919876543210", "body": "no, not interested", "when": 1}])
    comms = RecordingComms()
    processed, _ = process_inbound(sheets, comms, wa, last_poll=0)
    assert processed == 1
    assert sheets.read_all("Candidates")[0]["status"] == C_DECLINED
    assert not any(m == "interested_ack" for m, _ in comms.calls)


def test_unclear_reply_left_untouched():
    cand = _candidate()
    sheets = _sheets(cand)
    wa = FakeWa([{"from": "919876543210", "body": "i have a question", "when": 1}])
    processed, _ = process_inbound(sheets, RecordingComms(), wa, last_poll=0)
    assert processed == 0
    assert sheets.read_all("Candidates")[0]["status"] == C_CONTACTED


def test_unknown_phone_ignored():
    sheets = _sheets(_candidate())
    wa = FakeWa([{"from": "9988776655", "body": "yes", "when": 1}])
    processed, _ = process_inbound(sheets, RecordingComms(), wa, last_poll=0)
    assert processed == 0


def test_after_filter_respects_last_poll():
    sheets = _sheets(_candidate())
    wa = FakeWa([{"from": "919876543210", "body": "yes", "when": 2000}])
    processed, _ = process_inbound(sheets, RecordingComms(), wa, last_poll=3000)
    assert processed == 0