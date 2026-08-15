"""Checker verdict handling (Agent 5 on the sheet-driven path).

Polls the CheckerVerdicts sheet (keyed by educator email), then for each
`kyc_referred` candidate:
  * pass  -> advance to `accepted`, send the round-2 acceptance via A3
  * fail  -> `rejected`, rejection goes out over WhatsApp AND email via A3
Candidates with no verdict yet are left alone.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from config.schema import row_to_dict, update_row_by_index
from config.settings import settings
from core.sheets import SheetsClient
from graph.agents.a3_comms import CommsAgent
from graph.agents.a5_testing import parse_verdict
from graph.state import C_ACCEPTED, C_KYC_REFERRED, C_REJECTED

TEMPLATE_ACCEPT = (
    "Hi {name}, great news — you cleared the knowledge check! "
    "We'll be in touch shortly to schedule the next round with the centre."
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def poll_all_verdicts(sheets: SheetsClient) -> dict[str, str]:
    """email(lower) -> verdict for every row in the checker sheet."""
    result: dict[str, str] = {}
    for row in sheets.read_all(settings.sheet_checker_verdicts):
        email = (row.get("email") or row.get("educator_email") or "").strip().lower()
        verdict = parse_verdict(str(row.get("verdict", row.get("result", ""))))
        if email and verdict:
            result.setdefault(email, verdict)
    return result


def process_verdicts(sheets: SheetsClient, comms: CommsAgent) -> tuple[int, int]:
    """Returns (accepted, rejected)."""
    verdicts = poll_all_verdicts(sheets)
    if not verdicts:
        return 0, 0

    rows = sheets.read_range(settings.sheet_candidates)
    if not rows:
        return 0, 0
    headers = [str(h).strip() for h in rows[0]]
    accepted = rejected = 0
    for i, row in enumerate(rows[1:], start=2):
        cand = row_to_dict(headers, row)
        if cand.get("status") != C_KYC_REFERRED:
            continue
        verdict = verdicts.get(cand.get("educator_email", "").lower(), "")
        if not verdict:
            continue
        cand["verdict"] = verdict
        cand["updated_at"] = _now()
        if verdict == "pass":
            cand["status"] = C_ACCEPTED
            accept = TEMPLATE_ACCEPT.format(name=cand.get("educator_name", "there"))
            comms.send_whatsapp(cand.get("educator_phone", ""), accept, event_id=cand.get("event_id", ""))
            sheets.log(f"accepted {cand.get('educator_email')} — knowledge check passed", cand.get("event_id", ""), cand.get("educator_email"))
            accepted += 1
        elif verdict == "fail":
            cand["status"] = C_REJECTED
            comms.send_rejection(cand)
            sheets.log(f"rejected {cand.get('educator_email')} — knowledge check failed", cand.get("event_id", ""), cand.get("educator_email"))
            rejected += 1
        update_row_by_index(sheets, settings.sheet_candidates, i, cand)
    return accepted, rejected