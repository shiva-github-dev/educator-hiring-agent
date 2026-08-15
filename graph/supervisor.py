"""Agent 0 — the supervisor graph.

A0 owns the per-request hiring state machine. Specialist agents are nodes:
  - a2_shortlist: match + pipeline + RTH view
  - a3_outreach : first contact + follow-ups via Agent 3 (Comms)
  - a5_verdicts : poll checker sheet, accept/reject, fire rejection comms

Compiled with a SQLite checkpointer so threads survive restarts and the
tick scheduler can resume them.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import RetryPolicy

from config.settings import settings
from core.sheets import SheetsClient
from graph.agents.a2_shortlist import a2_shortlist_node
from graph.agents.a3_comms import CommsAgent
from graph.agents.a5_testing import a5_testing_node, poll_verdicts
from graph.state import (
    C_CONTACTED,
    C_INTERESTED,
    C_KYC_REFERRED,
    C_QUEUED,
    C_REJECTED,
    E_EVALUATING,
    HiringState,
)
from graph.tools.scheduling import is_due, next_follow_up_at

DB_PATH = Path(__file__).resolve().parent.parent / ".data" / "graph.db"

# Node-level retries for flaky external calls (WhatsApp/email/verdict polls).
RETRY_FLAKY = RetryPolicy(
    initial_interval=1.0,
    backoff_factor=2.0,
    max_interval=30.0,
    max_attempts=3,
    jitter=True,
)


class VerdictsProvider:
    def __init__(self, sheets: SheetsClient) -> None:
        self._sheets = sheets

    def fetch(self, state: HiringState) -> dict[str, str]:
        emails = [c["educator_email"] for c in state.get("candidates", [])]
        return poll_verdicts(self._sheets, state.get("event_id", ""), emails)


Node = Callable[[HiringState], dict[str, Any]]


def build_supervisor(
    *,
    sheets: SheetsClient,
    educators: list[dict[str, Any]],
    comms: CommsAgent,
    verdicts: VerdictsProvider,
    checkpointer: SqliteSaver | None = None,
) -> CompiledStateGraph:
    def a2(state: HiringState) -> dict[str, Any]:
        return a2_shortlist_node(state, sheets, educators)

    def a3_first_contact(state: HiringState) -> dict[str, Any]:
        """Send first outreach to queued candidates; mark them contacted."""
        req = {"event_id": state["event_id"], "subject": state["subject"], "exam": state["exam"], "location": state["location"]}
        out: list[dict[str, Any]] = []
        audit: list[str] = []
        for cand in state.get("candidates", []):
            if cand.get("status") == C_QUEUED:
                ok = comms.send_outreach(req, cand)
                updated = dict(cand)
                updated["status"] = C_CONTACTED if ok else C_QUEUED
                updated["next_action_at"] = next_follow_up_at(None)
                out.append(updated)
                audit.append(f"outreach sent to {cand['educator_email']}" if ok else f"outreach FAILED for {cand['educator_email']}")
            else:
                out.append(cand)
        return {"candidates": out, "status": E_EVALUATING, "audit": audit}

    def a5(state: HiringState) -> dict[str, Any]:
        verdicts_map = verdicts.fetch(state)
        result = a5_testing_node(state, sheets, verdicts_map)
        # Fire rejection comms for newly rejected candidates.
        audit = list(result.get("audit", []))
        out = list(result.get("candidates", state.get("candidates", [])))
        for cand in out:
            if cand.get("status") == C_REJECTED and cand.get("verdict") == "fail":
                wa_ok, email_ok = comms.send_rejection(cand)
                audit.append(f"rejection notified {cand['educator_email']} (wa={wa_ok}, email={email_ok})")
        return {"candidates": out, "audit": audit}

    g = StateGraph(HiringState)
    g.add_node("a2_shortlist", a2)
    g.add_node("a3_first_contact", a3_first_contact, retry_policy=RETRY_FLAKY)
    g.add_node("a5_verdicts", a5, retry_policy=RETRY_FLAKY)
    g.add_edge(START, "a2_shortlist")
    g.add_edge("a2_shortlist", "a3_first_contact")
    g.add_edge("a3_first_contact", "a5_verdicts")
    g.add_edge("a5_verdicts", END)

    return g.compile(checkpointer=checkpointer)


def default_db_checkpointer() -> SqliteSaver:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    return SqliteSaver(conn)


def default_supervisor(sheets: SheetsClient | None = None) -> CompiledStateGraph:
    sheets = sheets or SheetsClient()
    comms = CommsAgent(sheets=sheets)
    return build_supervisor(
        sheets=sheets,
        educators=sheets.read_all(settings.sheet_educators),
        comms=comms,
        verdicts=VerdictsProvider(sheets),
        checkpointer=default_db_checkpointer(),
    )


def start_event(graph: CompiledStateGraph, req: dict[str, Any]) -> dict[str, Any]:
    from graph.state import new_event_state

    event_id = req["event_id"]
    thread = {"configurable": {"thread_id": event_id}}
    return graph.invoke(new_event_state(event_id, req), thread)