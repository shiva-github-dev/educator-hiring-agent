"""Agent 5 — test ecosystem: poll checker verdicts and decide pass/fail."""
from __future__ import annotations

from typing import Any

from config.settings import settings
from core.sheets import SheetsClient
from graph.state import C_KYC_DONE, C_KYC_REFERRED, C_REJECTED, HiringState


def parse_verdict(text: str) -> str:
    """Heuristic parse of the checker verdict cell -> 'pass' | 'fail' | ''.

    Failure markers are checked first so that e.g. "failed — not recommended"
    resolves to 'fail' rather than 'pass'."""
    t = (text or "").strip().lower()
    if any(w in t for w in ("fail", "reject", "not cleared", "weak", "not recommend", "declined", "disqualified")):
        return "fail"
    if any(w in t for w in ("pass", "cleared", "qualified", "recommend")):
        return "pass"
    return ""


def poll_verdicts(client: SheetsClient, event_id: str, candidate_emails: list[str]) -> dict[str, str]:
    """Returns {educator_email: verdict} for candidates in this event who have a new verdict row."""
    rows = client.read_all(settings.sheet_checker_verdicts)
    wanted = set(candidate_emails)
    result: dict[str, str] = {}
    for row in rows:
        email = (row.get("email") or row.get("educator_email") or "").strip().lower()
        if email in wanted:
            verdict = parse_verdict(str(row.get("verdict", row.get("result", ""))))
            if verdict:
                result[email] = verdict
    return result


def a5_testing_node(state: HiringState, client: SheetsClient, verdicts: dict[str, str]) -> dict[str, Any]:
    """Advance candidates whose verdict arrived: pass -> kyc_done; fail -> rejected."""
    updated: list[dict[str, Any]] = []
    audit: list[str] = []
    for cand in state.get("candidates", []):
        email = cand["educator_email"].lower()
        if cand.get("status") == C_KYC_REFERRED and email in verdicts:
            cand = dict(cand)
            cand["verdict"] = verdicts[email]
            if verdicts[email] == "pass":
                cand["status"] = C_KYC_DONE
                audit.append(f"{email} passed knowledge check")
            else:
                cand["status"] = C_REJECTED
                audit.append(f"{email} failed knowledge check")
            updated.append(cand)
    if updated:
        return {"candidates": updated, "audit": audit}
    return {"audit": ["no new verdicts"]}
