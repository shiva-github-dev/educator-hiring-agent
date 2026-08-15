from config.schema import CANDIDATE_HEADERS, dict_to_row
from core.calendar import CalendarSlot, DemoCalendar
from graph.state import C_CONTACTED, C_DECLINED, C_INTERESTED
from scheduler.inbound import simulate_inbound
from tests.helpers import MemorySheets, RecordingComms

PHONE = "919876543210"


def _candidate(status=C_CONTACTED):
    return {
        "event_id": "e1", "educator_email": "a@x.com", "educator_phone": PHONE,
        "educator_name": "A", "status": status, "followup_count": 0,
        "next_action_at": "", "calendly_link": "", "verdict": "", "round2_slot": "",
        "calendar_event_id": "", "created_at": "2026-08-01T00:00:00+00:00",
    }


def _sheets():
    sheets = MemorySheets()
    sheets.seed("Candidates", CANDIDATE_HEADERS, [dict_to_row(CANDIDATE_HEADERS, _candidate())])
    sheets.seed("Log", ["message", "event_id", "candidate_email"], [])
    return sheets


def test_simulate_inbound_yes():
    sheets = _sheets()
    comms = RecordingComms()
    assert simulate_inbound(sheets, comms, PHONE, "yes")
    assert sheets.read_all("Candidates")[0]["status"] == C_INTERESTED
    assert any(m == "interested_ack" for m, _ in comms.calls)


def test_simulate_inbound_no():
    sheets = _sheets()
    assert simulate_inbound(sheets, RecordingComms(), PHONE, "no")
    assert sheets.read_all("Candidates")[0]["status"] == C_DECLINED


def test_simulate_inbound_unknown_phone_returns_false():
    sheets = _sheets()
    assert not simulate_inbound(sheets, RecordingComms(), "9988776655", "yes")


def test_demo_calendar_requires_no_creds():
    cal = DemoCalendar()
    assert cal.create_event("R2", CalendarSlot(start_iso="2026-08-20T11:00:00+00:00", end_iso="2026-08-20T12:00:00+00:00"), ["a@x.com"]) == "demo-event"


def test_seeder_idempotent_then_force(tmp_path, monkeypatch):
    from bootstrap import seed_demo

    sheets = MemorySheets()
    first = seed_demo.seed(client=sheets)
    assert first["educators"] == 12
    assert first["centres"] == 2
    assert first["requests"] == 1

    second = seed_demo.seed(client=sheets)
    assert second["educators"] == 0  # skipped — already seeded

    third = seed_demo.seed(client=sheets, force=True)
    assert third["educators"] == 12  # re-seeded