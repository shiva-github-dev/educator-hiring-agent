"""Graph state definitions and status constants for the hiring workflow."""
from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

# ---- Candidate statuses ---------------------------------------------------
C_QUEUED = "queued"
C_CONTACTED = "contacted"
C_FOLLOW_UP_1 = "follow_up_1"
C_FOLLOW_UP_2 = "follow_up_2"
C_FOLLOW_UP_3 = "follow_up_3"
C_INTERESTED = "interested"
C_DECLINED = "declined"
C_NO_RESPONSE = "no_response"
C_KYC_REFERRED = "kyc_referred"
C_KYC_DONE = "kyc_done"
C_ACCEPTED = "accepted"
C_REJECTED = "rejected"
C_ROUND2_SCHEDULING = "round2_scheduling"
C_ROUND2_CONFIRMED = "round2_confirmed"
C_HIRED = "hired"

# ---- Event statuses --------------------------------------------------------
E_NEW = "new"
E_MATCHING = "matching"
E_OUTREACH = "outreach_in_progress"
E_EVALUATING = "evaluating"
E_ROUND2 = "round2"
E_FILLED = "filled"
E_CLOSED = "closed"


class Candidate(TypedDict, total=False):
    event_id: str
    educator_email: str
    educator_phone: str
    educator_name: str
    status: str
    followup_count: int
    next_action_at: str
    calendly_link: str
    verdict: str
    round2_slot: str
    calendar_event_id: str
    created_at: str


class HiringState(TypedDict, total=False):
    event_id: str
    centre: str
    location: str
    subject: str
    exam: str
    min_experience: float
    hiring_type: str
    leaving_educator: str
    round2_educator_email: str
    round2_educator_phone: str
    status: str
    candidates: list[Candidate]
    rth_list: list[str]
    audit: Annotated[list[str], add]


def new_event_state(event_id: str, req: dict[str, Any]) -> HiringState:
    return {
        "event_id": event_id,
        "centre": req.get("centre", ""),
        "location": req.get("location", ""),
        "subject": req.get("subject", ""),
        "exam": req.get("exam", ""),
        "min_experience": float(req.get("min_experience", 0) or 0),
        "hiring_type": req.get("hiring_type", "fresh"),
        "leaving_educator": req.get("leaving_educator", ""),
        "round2_educator_email": req.get("round2_educator_email", ""),
        "round2_educator_phone": req.get("round2_educator_phone", ""),
        "status": E_NEW,
        "candidates": [],
        "rth_list": [],
        "audit": [],
    }
