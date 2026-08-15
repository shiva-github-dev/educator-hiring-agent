"""Structured error capture for the whole ecosystem.

Every failure is recorded in two places:
  1. the Log sheet (surfaces on the Agent 1 dashboard),
  2. logs/errors.jsonl on the VM (readable by a coding agent).

`capture_exception` is the single entry point — tick, nodes and agents all
route failures through it.
"""
from __future__ import annotations

import json
import traceback
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.settings import settings


@dataclass
class ErrorRecord:
    ts: str
    level: str
    source: str
    event_id: str
    thread_id: str
    node: str
    exc_type: str
    message: str
    traceback: str

    def to_jsonl(self) -> str:
        return json.dumps(asdict(self))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def errors_file() -> Path:
    path = Path(settings.logs_dir or "logs")
    path.mkdir(parents=True, exist_ok=True)
    return path / "errors.jsonl"


def append_error_record(record: ErrorRecord) -> None:
    try:
        with errors_file().open("a", encoding="utf-8") as fh:
            fh.write(record.to_jsonl() + "\n")
    except OSError:
        pass  # never let logging itself crash the pipeline


def capture_exception(
    exc: BaseException,
    *,
    source: str,
    event_id: str = "",
    thread_id: str = "",
    node: str = "",
    sheets: Any | None = None,
) -> ErrorRecord:
    """Record a failure to the JSONL file and (if a client is given) the Log sheet."""
    record = ErrorRecord(
        ts=_now(),
        level="ERROR",
        source=source,
        event_id=event_id,
        thread_id=thread_id or event_id,
        node=node,
        exc_type=type(exc).__name__,
        message=str(exc)[:1000],
        traceback="".join(traceback.format_exception(type(exc), exc, exc.__traceback__))[-4000:],
    )
    append_error_record(record)
    if sheets is not None:
        try:
            sheets.append_row(
                settings.sheet_log,
                [record.ts, record.level, event_id, thread_id, f"{source}::{node} {record.exc_type}: {record.message}"],
            )
        except Exception:  # noqa: BLE001
            pass
    return record


def load_error_records(event_id: str = "", limit: int = 50) -> list[dict[str, Any]]:
    """Read recent error records (optionally filtered by event) from the JSONL file."""
    records: list[dict[str, Any]] = []
    try:
        with errors_file().open("r", encoding="utf-8") as fh:
            lines = fh.readlines()[-limit:]
        for line in lines:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not event_id or rec.get("event_id") == event_id:
                records.append(rec)
    except OSError:
        pass
    return records