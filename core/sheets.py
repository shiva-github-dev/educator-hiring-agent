"""Google Sheets bridge.

Uses a service-account credential for read/write. Share the target
spreadsheet with the service-account email to grant access.
"""
from __future__ import annotations

from typing import Any

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config.settings import settings
from core.auth import service_account_credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]


class SheetsError(Exception):
    pass


class SheetsClient:
    def __init__(self, sa_json: str | None = None, spreadsheet_id: str | None = None) -> None:
        sa_json = sa_json or settings.gcp_sa_json
        if not sa_json:
            raise SheetsError("No GCP service-account JSON path configured (GCP_SA_JSON).")
        if settings.demo_mode:
            resolved = spreadsheet_id or settings.spreadsheet_id_demo or settings.spreadsheet_id
        else:
            resolved = spreadsheet_id or settings.spreadsheet_id
        self._spreadsheet_id = resolved
        if not self._spreadsheet_id:
            raise SheetsError("No spreadsheet id configured (SPREADSHEET_ID).")
        creds = service_account_credentials(SCOPES, raw=sa_json or None)
        self._service = build("sheets", "v4", credentials=creds)

    # ---- low level -------------------------------------------------------
    def _values(self, *args: str, **kwargs: Any) -> list[list[Any]]:
        request = (
            self._service.spreadsheets()
            .values()
            .get(spreadsheetId=self._spreadsheet_id, *args, **kwargs)
        )
        try:
            resp = request.execute()
        except HttpError as exc:
            raise SheetsError(f"Read failed: {exc}") from exc
        return resp.get("values", [])

    def read_range(self, sheet: str, rng: str = "A1:Z10000") -> list[list[Any]]:
        return self._values(range=f"{sheet}!{rng}")

    def read_all(self, sheet: str) -> list[dict[str, Any]]:
        """Read a sheet that has a header row, returning list of dicts keyed by header."""
        rows = self.read_range(sheet)
        if not rows:
            return []
        headers = [str(h).strip() for h in rows[0]]
        out: list[dict[str, Any]] = []
        for row in rows[1:]:
            out.append({headers[i]: row[i] if i < len(row) else "" for i in range(len(headers))})
        return out

    def append_row(self, sheet: str, row: list[Any]) -> None:
        body = {"values": [row]}
        try:
            self._service.spreadsheets().values().append(
                spreadsheetId=self._spreadsheet_id,
                range=f"{sheet}!A1",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body=body,
            ).execute()
        except HttpError as exc:
            raise SheetsError(f"Append failed for {sheet}: {exc}") from exc

    def update_row(self, sheet: str, row_index: int, values: list[Any]) -> None:
        """row_index is 1-based and includes the header row (0-based data index = row_index - 1)."""
        rng = f"{sheet}!A{row_index}:{chr(ord('A') + len(values) - 1)}{row_index}"
        body = {"values": [values]}
        try:
            self._service.spreadsheets().values().update(
                spreadsheetId=self._spreadsheet_id,
                range=rng,
                valueInputOption="RAW",
                body=body,
            ).execute()
        except HttpError as exc:
            raise SheetsError(f"Update failed for {sheet}: {exc}") from exc

    def log(self, message: str, event_id: str = "", candidate_email: str = "") -> None:
        from datetime import datetime, timezone

        self.append_row(
            settings.sheet_log,
            [datetime.now(timezone.utc).isoformat(), "INFO", event_id, candidate_email, message],
        )