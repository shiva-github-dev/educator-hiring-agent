"""Canonical Google Sheets schemas + read/write helpers.

Keeps header columns in one place so the dashboard, tick scheduler and
bootstrap stay consistent.
"""
from __future__ import annotations

from typing import Any

from config.settings import settings
from core.sheets import SheetsClient

CENTRE_REQUEST_HEADERS = [
    "event_id",
    "centre",
    "location",
    "subject",
    "exam",
    "min_experience",
    "hiring_type",
    "leaving_educator",
    "round2_educator_email",
    "round2_educator_phone",
    "status",
    "created_at",
    "updated_at",
]

CANDIDATE_HEADERS = [
    "event_id", "educator_email", "educator_phone", "educator_name", "status",
    "followup_count", "next_action_at", "calendly_link", "verdict",
    "round2_slot", "calendar_event_id", "created_at",
]

CENTRES_HEADERS = [
    "centre", "location", "educator_name", "educator_email",
    "educator_phone", "subject", "active",
]

DIAGNOSIS_HEADERS = [
    "event_id", "status", "error_type", "error_message", "report", "created_at", "updated_at",
]

PATCH_HEADERS = [
    "event_id", "diagnosis_id", "status", "diff", "test_result", "created_at", "updated_at",
]

RUN_STATE_HEADERS = [
    "event_id", "failure_count", "last_error", "last_error_ts", "status", "diagnosis_requested",
]

HEALTH_HEADERS = ["key", "value", "updated_at"]

ROUND2_HEADERS = [
    "event_id", "candidate_email", "state", "slots_json", "choice", "alt_text",
    "scheduled_at", "calendar_event_id", "reminder_at", "reminded_at", "created_at", "updated_at",
]


def headers_for(sheet: str, client: SheetsClient) -> list[str]:
    """Read the header row of a sheet (fallback to the canonical schema)."""
    rows = client.read_range(sheet, "A1:Z1")
    if rows and rows[0]:
        return [str(h).strip() for h in rows[0]]
    return CANONICAL.get(sheet, [])


def row_to_dict(headers: list[str], row: list[Any]) -> dict[str, Any]:
    return {headers[i]: row[i] if i < len(row) else "" for i in range(len(headers))}


def dict_to_row(headers: list[str], data: dict[str, Any]) -> list[Any]:
    return [data.get(h, "") for h in headers]


def read_all_dicts(client: SheetsClient, sheet: str) -> list[dict[str, Any]]:
    return client.read_all(sheet)


def read_new_requests(client: SheetsClient) -> list[tuple[int, dict[str, Any]]]:
    """CentreRequests rows with status == 'new'; returns (row_index_1based, data)."""
    rows = client.read_range(settings.sheet_centre_requests)
    if not rows:
        return []
    headers = [str(h).strip() for h in rows[0]]
    out: list[tuple[int, dict[str, Any]]] = []
    for i, row in enumerate(rows[1:], start=2):
        data = row_to_dict(headers, row)
        if data.get("status", "").strip().lower() == "new":
            out.append((i, data))
    return out


def update_request_row(client: SheetsClient, row_index: int, data: dict[str, Any]) -> None:
    headers = headers_for(settings.sheet_centre_requests, client)
    client.update_row(settings.sheet_centre_requests, row_index, dict_to_row(headers, data))


CANONICAL = {
    settings.sheet_centre_requests: CENTRE_REQUEST_HEADERS,
    settings.sheet_candidates: CANDIDATE_HEADERS,
    settings.sheet_centres: CENTRES_HEADERS,
    settings.sheet_diagnosis: DIAGNOSIS_HEADERS,
    settings.sheet_patch: PATCH_HEADERS,
    settings.sheet_run_state: RUN_STATE_HEADERS,
    settings.sheet_health: HEALTH_HEADERS,
    settings.sheet_round2: ROUND2_HEADERS,
}


def rows_with(client: SheetsClient, sheet: str, **filters: Any) -> list[tuple[int, dict[str, Any]]]:
    """Rows (1-based index incl. header) where every non-empty filter matches case-insensitively."""
    rows = client.read_range(sheet)
    if not rows:
        return []
    headers = [str(h).strip() for h in rows[0]]
    out: list[tuple[int, dict[str, Any]]] = []
    for i, row in enumerate(rows[1:], start=2):
        data = row_to_dict(headers, row)
        if all(str(data.get(k, "")).strip().lower() == str(v).strip().lower() for k, v in filters.items() if v):
            out.append((i, data))
    return out


def update_row_by_index(client: SheetsClient, sheet: str, row_index: int, data: dict[str, Any]) -> None:
    headers = headers_for(sheet, client)
    client.update_row(sheet, row_index, dict_to_row(headers, data))


def set_run_state(client: SheetsClient, event_id: str, **values: Any) -> None:
    """Upsert a RunState row for an event."""
    rows = rows_with(client, settings.sheet_run_state, event_id=event_id)
    if rows:
        idx, data = rows[0]
        data.update(values)
        update_row_by_index(client, settings.sheet_run_state, idx, data)
    else:
        data = {"event_id": event_id, "failure_count": 0, "last_error": "", "last_error_ts": "", "status": "", "diagnosis_requested": "no"}
        data.update(values)
        client.append_row(settings.sheet_run_state, dict_to_row(RUN_STATE_HEADERS, data))


def set_health(client: SheetsClient, key: str, value: str) -> None:
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    rows = rows_with(client, settings.sheet_health, key=key)
    if rows:
        idx, _ = rows[0]
        update_row_by_index(client, settings.sheet_health, idx, {"key": key, "value": value, "updated_at": now})
    else:
        client.append_row(settings.sheet_health, [key, value, now])


def record_heartbeat(client: SheetsClient, key: str = "last_tick_at") -> None:
    from datetime import datetime, timezone

    set_health(client, key, datetime.now(timezone.utc).isoformat())


def read_health(client: SheetsClient) -> dict[str, str]:
    out: dict[str, str] = {}
    for _, data in rows_with(client, settings.sheet_health):
        out[data.get("key", "")] = data.get("value", "")
    return out
