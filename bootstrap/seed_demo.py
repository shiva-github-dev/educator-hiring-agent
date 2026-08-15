"""Seed a demo spreadsheet so the live instance is instantly explorable.

Idempotent: skips when the Educators sheet already has data (unless --force).

Usage:
    python -m bootstrap.seed_demo              # seed (or skip if already seeded)
    python -m bootstrap.seed_demo --force      # wipe + re-seed

The demo spreadsheet is chosen via SPREADSHEET_ID_DEMO (or SPREADSHEET_ID).
"""
from __future__ import annotations

import argparse
import sys
import uuid
from datetime import datetime, timezone
from typing import Any

from config.schema import CENTRES_HEADERS, CENTRE_REQUEST_HEADERS, dict_to_row
from config.settings import settings
from core.sheets import SheetsClient, SheetsError

EDUCATOR_HEADERS = ["name", "email", "phone", "subjects", "years_exp", "exam", "cv_link"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sample_educators() -> list[dict[str, Any]]:
    rows = [
        ("Aarav Mehta", "aarav.mehta@example.com", "919000000001", "Physics", 4, "JEE"),
        ("Priya Nair", "priya.nair@example.com", "919000000002", "Physics, Chemistry", 6, "Both"),
        ("Rohan Kulkarni", "rohan.k@example.com", "919000000003", "Chemistry", 5, "NEET"),
        ("Sneha Iyer", "sneha.iyer@example.com", "919000000004", "Biology", 8, "NEET"),
        ("Vikram Singh", "vikram.s@example.com", "919000000005", "Mathematics", 3, "JEE"),
        ("Ananya Rao", "ananya.rao@example.com", "919000000006", "Maths", 7, "Both"),
        ("Kabir Khan", "kabir.khan@example.com", "919000000007", "Physics", 2, "JEE"),
        ("Divya Patel", "divya.patel@example.com", "919000000008", "Biology, Chemistry", 10, "NEET"),
        ("Farhan Ali", "farhan.ali@example.com", "919000000009", "Mathematics", 1, "JEE"),
        ("Meera Joshi", "meera.joshi@example.com", "919000000010", "Physics", 9, "Both"),
        ("Aditya Verma", "aditya.v@example.com", "919000000011", "Chemistry", 4, "JEE"),
        ("Nisha Gupta", "nisha.gupta@example.com", "919000000012", "Biology", 6, "Both"),
    ]
    return [
        {"name": n, "email": e, "phone": p, "subjects": s, "years_exp": y, "exam": x, "cv_link": ""}
        for n, e, p, s, y, x in rows
    ]


def sample_centres() -> list[dict[str, Any]]:
    return [
        dict_to_row(CENTRES_HEADERS, {
            "centre": "North Centre", "location": "Pune", "educator_name": "Dr. R. Deshmukh",
            "educator_email": "round2.north@example.com", "educator_phone": "919800000011",
            "subject": "Physics", "active": "true",
        }),
        dict_to_row(CENTRES_HEADERS, {
            "centre": "South Centre", "location": "Mumbai", "educator_name": "Prof. L. Menon",
            "educator_email": "round2.south@example.com", "educator_phone": "919800000022",
            "subject": "Chemistry", "active": "true",
        }),
    ]


def sample_request() -> dict[str, Any]:
    return dict_to_row(CENTRE_REQUEST_HEADERS, {
        "event_id": f"demo-{uuid.uuid4().hex[:8]}",
        "centre": "North Centre", "location": "Pune", "subject": "Physics",
        "exam": "JEE", "min_experience": 2, "hiring_type": "fresh",
        "leaving_educator": "", "round2_educator_email": "round2.north@example.com",
        "round2_educator_phone": "919800000011", "status": "new",
        "created_at": _now(), "updated_at": _now(),
    })


def _ensure_educators_tab(client: SheetsClient) -> None:
    if not hasattr(client, "_service"):
        return  # test doubles skip tab creation
    try:
        client.read_range(settings.sheet_educators, "A1:Z1")
    except SheetsError:
        from googleapiclient.errors import HttpError

        try:
            client._service.spreadsheets().batchUpdate(
                spreadsheetId=client._spreadsheet_id,
                body={"requests": [{"addSheet": {"properties": {"title": settings.sheet_educators}}}]},
            ).execute()
        except HttpError as exc:
            raise SheetsError(f"could not create Educators tab: {exc}") from exc


def seed(client: SheetsClient | None = None, force: bool = False) -> dict[str, int]:
    sheets = client or SheetsClient()
    _ensure_educators_tab(sheets)

    result = {"educators": 0, "centres": 0, "requests": 0}

    existing = sheets.read_all(settings.sheet_educators)
    if existing and not force:
        print("Educators already seeded — skipping (use --force to re-seed).")
    else:
        if not existing:
            sheets.append_row(settings.sheet_educators, EDUCATOR_HEADERS)
        for e in sample_educators():
            sheets.append_row(settings.sheet_educators, dict_to_row(EDUCATOR_HEADERS, e))
        result["educators"] = len(sample_educators())

    existing_centres = sheets.read_all(settings.sheet_centres)
    if not existing_centres or force:
        if not existing_centres:
            sheets.append_row(settings.sheet_centres, CENTRES_HEADERS)
        for c in sample_centres():
            sheets.append_row(settings.sheet_centres, c)
        result["centres"] = len(sample_centres())

    existing_reqs = sheets.read_all(settings.sheet_centre_requests)
    if not existing_reqs or force:
        if not existing_reqs:
            sheets.append_row(settings.sheet_centre_requests, CENTRE_REQUEST_HEADERS)
        sheets.append_row(settings.sheet_centre_requests, sample_request())
        result["requests"] = 1

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed the demo spreadsheet.")
    parser.add_argument("--force", action="store_true", help="wipe and re-seed")
    args = parser.parse_args()
    counts = seed(force=args.force)
    print(f"seeded: {counts}")
    return 0


if __name__ == "__main__":
    sys.exit(main())