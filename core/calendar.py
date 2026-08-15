"""Google Calendar integration for round-2 interviews (Milestone 4).

Creates events on the configured calendar (default: the service account's
primary calendar; set CALENDAR_ID to a shared calendar). Invites both the
candidate and the centre's round-2 educator.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config.settings import settings
from core.auth import service_account_credentials

CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar"


@dataclass
class CalendarSlot:
    start_iso: str
    end_iso: str
    timezone: str = "Asia/Kolkata"


class CalendarError(Exception):
    pass


class CalendarClient:
    def __init__(self, calendar_id: str | None = None) -> None:
        self._calendar_id = calendar_id or settings.calendar_id
        creds = service_account_credentials([CALENDAR_SCOPE])
        self._service = build("calendar", "v3", credentials=creds)

    def create_event(
        self,
        summary: str,
        slot: CalendarSlot,
        attendees: list[str],
        description: str = "",
    ) -> str:
        body = {
            "summary": summary,
            "description": description,
            "start": {"dateTime": slot.start_iso, "timeZone": slot.timezone},
            "end": {"dateTime": slot.end_iso, "timeZone": slot.timezone},
            "attendees": [{"email": a} for a in attendees if a],
        }
        try:
            event = (
                self._service.events()
                .insert(calendarId=self._calendar_id, body=body, sendUpdates="all")
                .execute()
            )
            return event.get("id", "")
        except HttpError as exc:
            raise CalendarError(f"create_event failed: {exc}") from exc

    def delete_event(self, event_id: str) -> None:
        try:
            self._service.events().delete(calendarId=self._calendar_id, eventId=event_id).execute()
        except HttpError as exc:
            raise CalendarError(f"delete_event failed: {exc}") from exc


def slot_end(start_iso: str, minutes: int = 60) -> str:
    start = datetime.fromisoformat(start_iso)
    return (start + timedelta(minutes=minutes)).isoformat()


class DemoCalendar:
    """No-credential stand-in for demo mode: logs instead of creating events."""

    def create_event(self, summary: str, slot: CalendarSlot, attendees: list[str], description: str = "") -> str:
        print(f"[DEMO CALENDAR] {summary} | {slot.start_iso} -> {slot.end_iso} | {', '.join(attendees)}")
        return "demo-event"

    def delete_event(self, event_id: str) -> None:
        print(f"[DEMO CALENDAR] delete {event_id}")


def calendar_for_mode() -> CalendarClient | DemoCalendar:
    if settings.demo_mode:
        return DemoCalendar()
    return CalendarClient()