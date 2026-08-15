from config.schema import CANDIDATE_HEADERS, dict_to_row
from graph.state import C_CONTACTED, C_INTERESTED, C_KYC_REFERRED
from scheduler.calendly import process_calendly
from tests.helpers import MemorySheets, RecordingComms


def _candidate(email, status=C_INTERESTED, link=""):
    return {
        "event_id": "e1", "educator_email": email, "educator_phone": "919876543210",
        "educator_name": "N", "status": status, "followup_count": 0,
        "next_action_at": "", "calendly_link": link, "verdict": "", "round2_slot": "",
        "calendar_event_id": "", "created_at": "2026-08-01T00:00:00+00:00",
    }


def _sheets(*cands):
    sheets = MemorySheets()
    sheets.seed("Candidates", CANDIDATE_HEADERS, [dict_to_row(CANDIDATE_HEADERS, c) for c in cands])
    sheets.seed("Log", ["message", "event_id", "candidate_email"], [])
    return sheets


def test_interest_sends_calendly_and_advances():
    sheets = _sheets(_candidate("a@x.com"))
    comms = RecordingComms()
    assert process_calendly(sheets, comms) == 1
    cand = sheets.read_all("Candidates")[0]
    assert cand["status"] == C_KYC_REFERRED
    assert "a%40x.com" in cand["calendly_link"] or "a@x.com" in cand["calendly_link"]
    assert any(m == "calendly" for m, _ in comms.calls)


def test_only_interested_candidates_get_links():
    sheets = _sheets(
        _candidate("a@x.com", status=C_INTERESTED),
        _candidate("b@x.com", status=C_CONTACTED),
    )
    sent = process_calendly(sheets, RecordingComms())
    assert sent == 1
    statuses = [c["status"] for c in sheets.read_all("Candidates")]
    assert statuses == [C_KYC_REFERRED, C_CONTACTED]


def test_already_referred_not_resent():
    sheets = _sheets(_candidate("a@x.com", status=C_KYC_REFERRED, link="https://calendly.com/x/1"))
    assert process_calendly(sheets, RecordingComms()) == 0