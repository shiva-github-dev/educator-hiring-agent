from config.schema import CANDIDATE_HEADERS, dict_to_row
from graph.state import C_ACCEPTED, C_KYC_REFERRED, C_REJECTED
from scheduler.verdicts import process_verdicts
from tests.helpers import MemorySheets, RecordingComms


def _candidate(email, status=C_KYC_REFERRED):
    return {
        "event_id": "e1", "educator_email": email, "educator_phone": "919876543210",
        "educator_name": email.split("@")[0], "status": status, "followup_count": 0,
        "next_action_at": "", "calendly_link": "", "verdict": "", "round2_slot": "",
        "calendar_event_id": "", "created_at": "2026-08-01T00:00:00+00:00",
    }


def _setup(candidates, verdicts):
    sheets = MemorySheets()
    sheets.seed("Candidates", CANDIDATE_HEADERS, [dict_to_row(CANDIDATE_HEADERS, c) for c in candidates])
    sheets.seed("CheckerVerdicts", ["event_id", "email", "verdict", "created_at"], verdicts)
    sheets.seed("Log", ["message", "event_id", "candidate_email"], [])
    return sheets


def test_pass_accepts_fail_rejects():
    sheets = _setup(
        [_candidate("a@x.com"), _candidate("b@x.com"), _candidate("c@x.com")],
        [["e1", "a@x.com", "PASS", "ts"], ["e1", "b@x.com", "FAIL - not recommended", "ts"]],
    )
    comms = RecordingComms()
    accepted, rejected = process_verdicts(sheets, comms)
    assert (accepted, rejected) == (1, 1)
    by_email = {c["educator_email"]: c["status"] for c in sheets.read_all("Candidates")}
    assert by_email == {"a@x.com": C_ACCEPTED, "b@x.com": C_REJECTED, "c@x.com": C_KYC_REFERRED}
    assert any(m == "rejection" for m, _ in comms.calls)


def test_no_verdict_no_move():
    sheets = _setup([_candidate("a@x.com")], [["e1", "a@x.com", "in progress", "ts"]])
    accepted, rejected = process_verdicts(sheets, RecordingComms())
    assert (accepted, rejected) == (0, 0)
    assert sheets.read_all("Candidates")[0]["status"] == C_KYC_REFERRED