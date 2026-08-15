"""Pure candidate-matching logic (no I/O) — unit-testable."""

from __future__ import annotations

from typing import Any

# Subject normalization (lowercased, synonym-mapped).
SUBJECT_SYNONYMS = {
    "math": "mathematics",
    "maths": "mathematics",
    "physics": "physics",
    "phys": "physics",
    "numeric": "mathematics",
    "chemistry": "chemistry",
    "chem": "chemistry",
    "biology": "biology",
    "bio": "biology",
    "biotechnology": "biology",
    "statistics": "mathematics",
}

EXAM_JEE = "jee"
EXAM_NEET = "neet"
EXAM_BOTH = "both"


def _clean(value: Any) -> str:
    return str(value or "").strip().lower()


def normalize_subject(subject: str) -> str:
    s = _clean(subject)
    return SUBJECT_SYNONYMS.get(s, s)


def normalize_exam(exam: str) -> str:
    e = _clean(exam)
    if "jee" in e and "neet" in e:
        return EXAM_BOTH
    if "jee" in e:
        return EXAM_JEE
    if "neet" in e:
        return EXAM_NEET
    return e


def parse_experience(value: Any) -> float:
    try:
        return float(str(value or 0).replace(",", "").strip())
    except (TypeError, ValueError):
        return 0.0


def subject_overlap(educator_subjects: Any, request_subject: str) -> bool:
    req = normalize_subject(request_subject)
    if not req:
        return True  # no subject specified → don't filter on subject
    subjects = _clean(educator_subjects).split(",")
    return any(normalize_subject(s) == req for s in subjects if s.strip())


def exam_matches(educator_exam: Any, request_exam: str) -> bool:
    """educator covers request: for 'both' request the educator must cover both;"""
    """for 'jee'/'neet' request either a single or 'both' coverage is acceptable."""
    e = normalize_exam(educator_exam)
    r = normalize_exam(request_exam)
    if not r:
        return e in {EXAM_JEE, EXAM_NEET, EXAM_BOTH}
    if not e:
        return False
    if r == EXAM_BOTH:
        return e == EXAM_BOTH
    return e in {r, EXAM_BOTH}


def _cell(educator: dict[str, Any], *keys: str) -> str:
    lowered = {k.lower(): v for k, v in educator.items()}
    for key in keys:
        if key.lower() in lowered:
            return str(lowered[key.lower()] or "")
    return ""


def matches(educator: dict[str, Any], request: dict[str, Any]) -> bool:
    years = parse_experience(_cell(educator, "years_exp", "years_of_experience", "years exp", "experience", "years"))
    min_exp = parse_experience(request.get("min_experience", 0))
    if min_exp and years < min_exp:
        return False
    if not subject_overlap(_cell(educator, "subjects", "subjects taught", "subject"), request.get("subject", "")):
        return False
    if not exam_matches(_cell(educator, "exam", "jee/neet", "target_exam"), request.get("exam", "")):
        return False
    return True


def build_contact_pipeline(educators: list[dict[str, Any]], request: dict[str, Any]) -> list[dict[str, Any]]:
    """Filter educators by the request; returns shortlisted candidates in original order."""
    return [e for e in educators if matches(e, request)]


def contact_phone(educator: dict[str, Any]) -> str:
    return _cell(educator, "phone", "mobile", "phone number", "contact", "whatsapp")


def contact_email(educator: dict[str, Any]) -> str:
    return _cell(educator, "email", "email address")