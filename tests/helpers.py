"""Shared test doubles for scheduler/inbound and follow-up tests."""

from __future__ import annotations


class MemorySheets:
    """Minimal SheetsClient stand-in backed by in-memory row lists."""

    def __init__(self) -> None:
        self._data: dict[str, list[list]] = {}
        self.appends: list[tuple[str, list]] = []

    def _rows(self, sheet: str) -> list[list]:
        return self._data.setdefault(sheet, [])

    def read_range(self, sheet: str, rng: str = "A1:Z10000") -> list[list]:
        return self._rows(sheet)

    def read_all(self, sheet: str) -> list[dict]:
        rows = self._rows(sheet)
        if not rows:
            return []
        headers = rows[0]
        return [{headers[i]: (row[i] if i < len(row) else "") for i in range(len(headers))} for row in rows[1:]]

    def append_row(self, sheet: str, row: list) -> None:
        self._rows(sheet).append(row)
        self.appends.append((sheet, row))

    def update_row(self, sheet: str, row_index: int, values: list) -> None:
        self._rows(sheet)[row_index - 1] = values

    def log(self, message: str, event_id: str = "", candidate_email: str = "") -> None:
        self.append_row("Log", [message, event_id, candidate_email])

    def seed(self, sheet: str, headers: list, rows: list[list]) -> None:
        self._rows(sheet).append(headers)
        self._rows(sheet).extend(rows)


class FakeWa:
    """Stand-in for WhatsAppClient.inbox."""

    def __init__(self, messages: list[dict] | None = None, ready: bool = True) -> None:
        self.messages = messages or []
        self.ready = ready

    def inbox(self, after: int = 0) -> list[dict]:
        return [m for m in self.messages if m["when"] > after]

    def is_ready(self) -> bool:
        return self.ready


class RecordingComms:
    """Records CommsAgent calls; every send succeeds."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def _record(self, method: str, cand: dict) -> bool:
        self.calls.append((method, dict(cand)))
        return True

    def send_outreach(self, req, cand):
        return self._record("outreach", cand)

    def send_follow_up(self, req, cand):
        return self._record("follow_up", cand)

    def send_interested_ack(self, cand):
        return self._record("interested_ack", cand)

    def send_calendly(self, cand, link):
        return self._record("calendly", cand)

    def send_whatsapp(self, to_number, text, *, event_id="", email=""):
        self.calls.append(("whatsapp", {"to": to_number, "text": text, "event_id": event_id}))
        return True

    def send_rejection(self, cand):
        return self._record("rejection", cand), self._record("rejection_email", cand)