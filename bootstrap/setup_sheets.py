"""One-time bootstrap: create the missing worksheet tabs + header rows.

Usage: python -m bootstrap.setup_sheets
Requires GCP_SA_JSON + SPREADSHEET_ID in .env and the SA shared on the doc.
"""
from __future__ import annotations

from googleapiclient.errors import HttpError

from config.schema import (
    CANONICAL,
    CENTRE_REQUEST_HEADERS,
    CANDIDATE_HEADERS,
    CENTRES_HEADERS,
    DIAGNOSIS_HEADERS,
    HEALTH_HEADERS,
    PATCH_HEADERS,
    ROUND2_HEADERS,
    RUN_STATE_HEADERS,
)
from config.settings import settings
from core.sheets import SheetsClient

CHECKER_VERDICT_HEADERS = ["event_id", "email", "verdict", "created_at"]
LOG_HEADERS = ["timestamp", "level", "event_id", "candidate_email", "message"]


def existing_sheets(client: SheetsClient) -> set[str]:
    meta = client._service.spreadsheets().get(
        spreadsheetId=client._spreadsheet_id, fields="sheets.properties.title"
    ).execute()
    return {s["properties"]["title"] for s in meta.get("sheets", [])}


def add_sheet(client: SheetsClient, title: str) -> None:
    body = {"requests": [{"addSheet": {"properties": {"title": title}}}]}
    try:
        client._service.spreadsheets().batchUpdate(
            spreadsheetId=client._spreadsheet_id, body=body
        ).execute()
        print(f"created sheet: {title}")
    except HttpError as exc:
        print(f"could not create {title}: {exc}")


def main() -> None:
    client = SheetsClient()
    have = existing_sheets(client)

    targets = {
        settings.sheet_centres: CENTRES_HEADERS,
        settings.sheet_centre_requests: CENTRE_REQUEST_HEADERS,
        settings.sheet_candidates: CANDIDATE_HEADERS,
        settings.sheet_checker_verdicts: CHECKER_VERDICT_HEADERS,
        settings.sheet_log: LOG_HEADERS,
        settings.sheet_diagnosis: DIAGNOSIS_HEADERS,
        settings.sheet_patch: PATCH_HEADERS,
        settings.sheet_run_state: RUN_STATE_HEADERS,
        settings.sheet_health: HEALTH_HEADERS,
        settings.sheet_round2: ROUND2_HEADERS,
    }
    for title, headers in targets.items():
        if title not in have:
            add_sheet(client, title)
        existing = client.read_range(title, "A1:Z1")
        if not existing or not existing[0]:
            client.append_row(title, headers)
            print(f"wrote headers to {title}")
        else:
            print(f"ok: {title} already has headers")

    print("Bootstrap done.")


if __name__ == "__main__":
    main()