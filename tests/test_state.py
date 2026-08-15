from graph.state import C_QUEUED, E_NEW, new_event_state


def test_new_event_state():
    state = new_event_state("evt-1", {
        "centre": "C1", "location": "Pune", "subject": "Physics", "exam": "JEE",
        "min_experience": "2", "hiring_type": "replacement", "leaving_educator": "L",
        "round2_educator_email": "r@x.com", "round2_educator_phone": "999",
    })
    assert state["event_id"] == "evt-1"
    assert state["min_experience"] == 2.0
    assert state["status"] == E_NEW
    assert state["candidates"] == []
    assert state["rth_list"] == []


def test_audit_reducer_appends():
    state = new_event_state("evt-2", {"centre": "C", "location": "L", "subject": "S", "exam": "JEE"})
    state["audit"] += ["a"]
    state["audit"] += ["b"]
    assert state["audit"] == ["a", "b"]


def test_candidate_defaults():
    from graph.state import Candidate

    cand: Candidate = {"event_id": "e", "educator_email": "c@x.com"}
    assert cand.get("status") is None
    assert C_QUEUED == "queued"