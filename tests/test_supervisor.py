from langgraph.checkpoint.memory import InMemorySaver

from graph.agents.a2_shortlist import a2_shortlist_node, rth_subset
from graph.agents.a3_comms import CommsAgent
from graph.agents.a5_testing import a5_testing_node, parse_verdict
from graph.state import (
    C_ACCEPTED,
    C_INTERESTED,
    C_KYC_DONE,
    C_KYC_REFERRED,
    C_QUEUED,
    new_event_state,
)
from graph.supervisor import build_supervisor

EDUCATORS = [
    {"name": "A", "email": "a@x.com", "phone": "1", "subjects": "Maths", "years_exp": 3, "exam": "JEE"},
    {"name": "B", "email": "b@x.com", "phone": "2", "subjects": "Physics", "years_exp": 5, "exam": "Both"},
]


class FakeSheets:
    def __init__(self):
        self.appends: list[tuple[str, list]] = []

    def read_all(self, sheet):
        return []

    def read_range(self, sheet, rng="A1:Z1"):
        return []

    def append_row(self, sheet, row):
        self.appends.append((sheet, row))

    def update_row(self, sheet, row_index, values):
        pass

    def log(self, message, event_id="", candidate_email=""):
        self.appends.append(("Log", [message, event_id]))


class FakeVerdicts:
    def __init__(self, mapping):
        self.mapping = mapping

    def fetch(self, state):
        return {c["educator_email"]: v for c in state["candidates"] if c["educator_email"] in self.mapping}


def test_a2_shortlist_node_persists():
    sheets = FakeSheets()
    state = new_event_state("e1", {"centre": "C", "location": "P", "subject": "Physics", "exam": "JEE", "min_experience": 2})
    out = a2_shortlist_node(state, sheets, EDUCATORS)
    assert len(out["candidates"]) == 1
    assert out["candidates"][0]["educator_email"] == "b@x.com"
    assert out["status"] == "outreach_in_progress"
    assert len(sheets.appends) == 1


def test_rth_definition_is_interested_subset():
    cands = [
        {"educator_email": "x", "status": C_INTERESTED, "created_at": "1"},
        {"educator_email": "y", "status": C_KYC_REFERRED, "created_at": "2"},
        {"educator_email": "z", "status": C_ACCEPTED, "created_at": "3"},
        {"educator_email": "w", "status": C_QUEUED, "created_at": "4"},
    ]
    subset = rth_subset(cands)
    assert subset == ["x", "y", "z"]  # interested + advanced (not yet hired), excluded queued


def test_parse_verdict():
    assert parse_verdict("Candidate cleared the interview") == "pass"
    assert parse_verdict("FAIL — not recommended") == "fail"
    assert parse_verdict("in progress") == ""


def test_a5_updates_status():
    state = new_event_state("e1", {"centre": "C", "location": "P", "subject": "S", "exam": "JEE"})
    state["candidates"] = [
        {"event_id": "e1", "educator_email": "c@x.com", "educator_phone": "9", "status": C_KYC_REFERRED},
    ]
    out = a5_testing_node(state, FakeSheets(), {"c@x.com": "pass"})
    assert out["candidates"][0]["status"] == C_KYC_DONE
    assert out["candidates"][0]["verdict"] == "pass"


def test_supervisor_end_to_end():
    graph = build_supervisor(
        sheets=FakeSheets(),
        educators=EDUCATORS,
        comms=CommsAgent(dry_run=True),
        verdicts=FakeVerdicts({}),
        checkpointer=InMemorySaver(),
    )
    req = {"event_id": "evt-x", "centre": "C", "location": "P", "subject": "Physics", "exam": "JEE", "min_experience": 4}
    result = graph.invoke(new_event_state(req["event_id"], req), {"configurable": {"thread_id": req["event_id"]}})
    assert result["candidates"][0]["status"] == "contacted"
    assert [c["educator_email"] for c in result["candidates"]] == ["b@x.com"]