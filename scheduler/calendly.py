"""Send the Calendly link to interested candidates (AI knowledge check).

Scans Candidates for `interested` status once per tick: builds an
email-prefilled Calendly link, sends it via Agent 3, and advances the
candidate to `kyc_referred`. Guarded so a candidate only ever gets one link.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from config.schema import row_to_dict, update_row_by_index
from config.settings import settings
from core.sheets import SheetsClient
from graph.agents.a3_comms import CommsAgent
from graph.state import C_INTERESTED, C_KYC_REFERRED
from graph.tools.scheduling import build_calendly_link


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def process_calendly(sheets: SheetsClient, comms: CommsAgent) -> int:
    """Returns the number of Calendly links sent."""
    rows = sheets.read_range(settings.sheet_candidates)
    if not rows:
        return 0
    headers = [str(h).strip() for h in rows[0]]
    sent = 0
    for i, row in enumerate(rows[1:], start=2):
        cand = row_to_dict(headers, row)
        if cand.get("status") != C_INTERESTED:
            continue
        email = cand.get("educator_email", "")
        if not email:
            continue
        link = build_calendly_link(email)
        ok = comms.send_calendly(cand, link)
        cand["status"] = C_KYC_REFERRED
        cand["calendly_link"] = link
        cand["updated_at"] = _now()
        update_row_by_index(sheets, settings.sheet_candidates, i, cand)
        sheets.log(f"calendly link sent to {email}", cand.get("event_id", ""), email)
        sent += 1
        if not ok:
            sheets.log(f"WARN: calendly send returned failure for {email}", cand.get("event_id", ""), email)
    return sent