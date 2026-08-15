"""Tests for Milestone 1.5 error handling and Agent 6."""
from __future__ import annotations

from pathlib import Path

from graph.agents import a6_support
from scheduler import tick

from tests.helpers import MemorySheets


def test_capture_exception_writes_jsonl(tmp_path: Path, monkeypatch) -> None:
    from core import errors

    monkeypatch.setattr(errors, "errors_file", lambda: tmp_path / "errors.jsonl")
    rec = errors.capture_exception(ValueError("boom"), source="tick", event_id="e1", node="start")
    assert rec.exc_type == "ValueError"
    assert (tmp_path / "errors.jsonl").exists()
    loaded = errors.load_error_records(event_id="e1")
    assert loaded and loaded[0]["message"] == "boom"


def test_breaker_trips_and_enqueues_diagnosis() -> None:
    sheets = MemorySheets()
    sheets.seed("CentreRequests", ["event_id", "status"], [["e1", "new"]])
    sheets.seed("RunState", ["event_id", "failure_count", "last_error", "last_error_ts", "status", "diagnosis_requested"], [])
    sheets.seed("Diagnosis", ["event_id", "status", "error_type", "error_message", "report", "created_at", "updated_at"], [])
    sheets.seed("Health", ["key", "value", "updated_at"], [])

    tripped = False
    for _ in range(3):
        tripped = tick._bump_failure(sheets, "e1", ValueError("x"))
    assert tripped
    run_state = sheets.read_all("RunState")
    assert run_state[-1]["status"] == "error"
    assert run_state[-1]["diagnosis_requested"] == "yes"
    diag = sheets.read_all("Diagnosis")
    assert diag and diag[-1]["status"] == "queued"


def test_reset_run_state() -> None:
    sheets = MemorySheets()
    sheets.seed("RunState", ["event_id", "failure_count", "last_error", "last_error_ts", "status", "diagnosis_requested"], [])
    tick._reset_run_state(sheets, "e2")
    assert sheets.read_all("RunState")[-1]["status"] == "ok"


def test_diagnosis_queue_processes_with_fake_llm(monkeypatch) -> None:
    sheets = MemorySheets()
    sheets.seed("Diagnosis", ["event_id", "status", "error_type", "error_message", "report", "created_at", "updated_at"], [])
    sheets.seed("Log", ["ts", "level", "event_id", "candidate_email", "message"], [])

    from core import errors

    monkeypatch.setattr(errors, "errors_file", lambda: Path("logs") / "errors.jsonl")
    a6_support.enqueue_diagnosis(sheets, "e1", "ValueError", "boom")

    class FakeModel:
        def invoke(self, prompt):
            class C:
                content = "ROOT_CAUSE: test\nSUGGESTED_FIX: none"
            return C()

    monkeypatch.setattr(a6_support, "get_chat_model", lambda: FakeModel())
    assert a6_support.process_diagnosis_queue(sheets) == 1
    diag = sheets.read_all("Diagnosis")
    assert diag[-1]["status"] == "done"
    assert "ROOT_CAUSE" in diag[-1]["report"]


def test_sandbox_fix_requires_cli() -> None:
    sheets = MemorySheets()
    sheets.seed("Diagnosis", ["event_id", "status", "error_type", "error_message", "report", "created_at", "updated_at"], [])
    a6_support.enqueue_diagnosis(sheets, "e1", "ValueError", "boom")
    # OPENCODE_CLI is empty in test env
    result = a6_support.run_sandbox_fix(sheets, "e1", 2)
    assert result["status"] == "manual"


def test_sync_candidates_writes_status_back():
    from config.schema import CANDIDATE_HEADERS, dict_to_row
    from scheduler.tick import sync_candidates

    sheets = MemorySheets()
    sheets.seed("Candidates", CANDIDATE_HEADERS, [dict_to_row(CANDIDATE_HEADERS, {
        "event_id": "e1", "educator_email": "a@x.com", "educator_phone": "1",
        "educator_name": "A", "status": "queued", "followup_count": 0, "next_action_at": "",
        "calendly_link": "", "verdict": "", "round2_slot": "", "calendar_event_id": "",
        "created_at": "2026-08-01T00:00:00+00:00",
    })])
    result = {"event_id": "e1", "candidates": [
        {"educator_email": "a@x.com", "status": "contacted", "followup_count": 0, "next_action_at": "2026-08-02T00:00:00+00:00"},
    ]}
    assert sync_candidates(sheets, result) == 1
    row = sheets.read_all("Candidates")[0]
    assert row["status"] == "contacted"
    assert row["next_action_at"] == "2026-08-02T00:00:00+00:00"


def test_heartbeat_recorded() -> None:
    from config.schema import read_health, record_heartbeat

    sheets = MemorySheets()
    sheets.seed("Health", ["key", "value", "updated_at"], [])
    record_heartbeat(sheets, "last_tick_at")
    health = read_health(sheets)
    assert health.get("last_tick_at", "") != ""