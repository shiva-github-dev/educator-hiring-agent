"""Round-2 interview scheduling (A4 logic on the sheet-driven path).

State machine, one Row in the `Round2` sheet per (event, candidate):

  awaiting_educator_slots -> educator_slots_received
  educator_slots_received -> awaiting_candidate_choice
  awaiting_candidate_choice -> candidate_chosen | awaiting_candidate_alt
  awaiting_candidate_alt -> candidate_chosen        (educator confirms alt)
  candidate_chosen -> confirmed                     (Calendar event created)
  confirmed -> done                                 (reminders sent)

All messaging goes through Agent 3 (Comms).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from config.schema import ROUND2_HEADERS, dict_to_row, row_to_dict, rows_with, update_row_by_index
from config.settings import settings
from core.calendar import CalendarClient, CalendarSlot, CalendarError, slot_end
from core.sheets import SheetsClient
from graph.agents.a3_comms import CommsAgent
from graph.state import C_ACCEPTED
from graph.tools.scheduling import compute_reminder_at, propose_slots_to_candidate
from scheduler.followups import get_request


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _all_rows(sheets: SheetsClient) -> tuple[list[str], dict[int, dict[str, Any]]]:
    rows = sheets.read_range(settings.sheet_round2)
    if not rows:
        return [], {}
    headers = [str(h).strip() for h in rows[0]]
    data: dict[int, dict[str, Any]] = {}
    for i, row in enumerate(rows[1:], start=2):
        data[i] = row_to_dict(headers, row)
    return headers, data


def _candidate_by_email(sheets: SheetsClient, email: str) -> dict[str, Any]:
    for row in sheets.read_all(settings.sheet_candidates):
        if str(row.get("educator_email", "")).strip().lower() == email.strip().lower():
            return row
    return {}


def exists_for_event(rows: dict[int, dict[str, Any]], event_id: str) -> bool:
    return any(r.get("event_id") == event_id for r in rows.values())


def parse_slots(text: str) -> list[str]:
    out: list[str] = []
    for line in str(text).splitlines():
        line = line.strip().lstrip("-*•>").strip()
        if line and line not in out:
            out.append(line)
    return out


def start_round2(sheets: SheetsClient, comms: CommsAgent) -> int:
    """Create a Round2 row + ask the centre educator for slots for each accepted candidate."""
    _, rows = _all_rows(sheets)
    started = 0
    for cand in sheets.read_all(settings.sheet_candidates):
        if cand.get("status") != C_ACCEPTED:
            continue
        event_id = cand.get("event_id", "")
        if exists_for_event(rows, event_id):
            continue  # one negotiation per event (confirm_error needs manual fix, not a new one)
        req = get_request(sheets, event_id)
        educator_phone = req.get("round2_educator_phone", "")
        if not educator_phone:
            sheets.log(f"round2: no round2_educator_phone for event {event_id}", event_id)
            continue
        text = (
            f"Please share 3-5 time slots (date + time) for the round-2 interview "
            f"with {cand.get('educator_name')} ({req.get('subject')} at {req.get('location')}). "
            "One slot per line, e.g.:\n2026-08-20T11:00:00\n2026-08-21T17:30:00"
        )
        comms.send_whatsapp(educator_phone, text, event_id=event_id, email=cand.get("educator_email"))
        now = _now()
        sheets.append_row(
            settings.sheet_round2,
            dict_to_row(ROUND2_HEADERS, {
                "event_id": event_id, "candidate_email": cand.get("educator_email"),
                "state": "awaiting_educator_slots", "slots_json": "", "choice": "", "alt_text": "",
                "scheduled_at": "", "calendar_event_id": "", "reminder_at": "",
                "reminded_at": "", "created_at": now, "updated_at": now,
            }),
        )
        sheets.log(f"round2 started for {cand.get('educator_email')}; slot request sent to educator", event_id, cand.get("educator_email"))
        started += 1
    return started


def process_round2_inbound(sheets: SheetsClient, comms: CommsAgent, from_number: str, body: str) -> bool:
    """Handle a slot-proposal reply. Educator → slots/alt-confirm; candidate → choice/alt."""
    _, rows = _all_rows(sheets)
    target_phone = "".join(ch for ch in from_number or "" if ch.isdigit())[-10:]

    for idx, data in rows.items():
        if data.get("state") not in {"awaiting_educator_slots", "awaiting_candidate_choice", "awaiting_candidate_alt"}:
            continue
        event_id = data.get("event_id", "")
        req = get_request(sheets, event_id)
        educator_phone = "".join(ch for ch in str(req.get("round2_educator_phone", "")) if ch.isdigit())[-10:]
        cand = _candidate_by_email(sheets, data.get("candidate_email", ""))
        cand_phone = "".join(ch for ch in str(cand.get("educator_phone", "")) if ch.isdigit())[-10:]

        if target_phone == educator_phone and data.get("state") == "awaiting_educator_slots":
            slots = parse_slots(body)
            if not slots:
                comms.send_whatsapp(educator_phone, "Sorry, I couldn't read those slots. Please send one slot per line, e.g.\n2026-08-20T11:00:00", event_id=event_id)
                data["updated_at"] = _now()
                update_row_by_index(sheets, settings.sheet_round2, idx, data)
                return True
            data["state"] = "awaiting_candidate_choice"
            data["slots_json"] = json.dumps(slots)
            data["updated_at"] = _now()
            update_row_by_index(sheets, settings.sheet_round2, idx, data)
            proposal = propose_slots_to_candidate(slots)
            comms.send_whatsapp(cand_phone, proposal, event_id=event_id, email=cand.get("educator_email"))
            sheets.log(f"round2: slots proposed to {cand.get('educator_email')}", event_id, cand.get("educator_email"))
            return True

        if target_phone == cand_phone and data.get("state") == "awaiting_candidate_choice":
            slots = json.loads(data.get("slots_json", "[]") or "[]")
            try:
                choice_no = int(body.strip())
            except ValueError:
                choice_no = 0
            if 1 <= choice_no <= len(slots):
                data["state"] = "candidate_chosen"
                data["choice"] = slots[choice_no - 1]
                data["updated_at"] = _now()
                update_row_by_index(sheets, settings.sheet_round2, idx, data)
                sheets.log(f"round2: candidate {cand.get('educator_email')} chose {slots[choice_no - 1]}", event_id, cand.get("educator_email"))
            else:
                data["state"] = "awaiting_candidate_alt"
                data["alt_text"] = body[:500]
                data["updated_at"] = _now()
                update_row_by_index(sheets, settings.sheet_round2, idx, data)
                comms.send_whatsapp(
                    educator_phone,
                    f"Candidate {cand.get('educator_name')} couldn't take your slots and prefers: {body}. Confirm this or send alternatives.",
                    event_id=event_id,
                    email=cand.get("educator_email"),
                )
                sheets.log(f"round2: candidate {cand.get('educator_email')} prefers alt slot {body}", event_id, cand.get("educator_email"))
            return True

        if target_phone == educator_phone and data.get("state") == "awaiting_candidate_alt":
            data["state"] = "candidate_chosen"
            data["choice"] = body[:200]
            data["updated_at"] = _now()
            update_row_by_index(sheets, settings.sheet_round2, idx, data)
            sheets.log(f"round2: educator confirmed alt slot {body}", event_id, cand.get("educator_email"))
            return True

    return False


def confirm_round2(sheets: SheetsClient, comms: CommsAgent, calendar: CalendarClient) -> int:
    """Create the Calendar event + confirmations/reminder for candidate_chosen rows."""
    _, rows = _all_rows(sheets)
    confirmed = 0
    for idx, data in rows.items():
        if data.get("state") != "candidate_chosen":
            continue
        event_id = data.get("event_id", "")
        cand = _candidate_by_email(sheets, data.get("candidate_email", ""))
        req = get_request(sheets, event_id)
        slot = str(data.get("choice", "")).strip()
        try:
            start = datetime.fromisoformat(slot)
            if start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)
            start_iso = start.isoformat()
        except ValueError:
            data["state"] = "confirm_error"
            data["updated_at"] = _now()
            update_row_by_index(sheets, settings.sheet_round2, idx, data)
            sheets.log(f"round2: unparseable slot '{slot}' for {cand.get('educator_email')} — needs manual fix", event_id, cand.get("educator_email"))
            continue
        try:
            summary = f"Round 2 Interview — {req.get('subject', '')} at {req.get('location', '')}"
            event_id_out = calendar.create_event(
                summary=summary,
                slot=CalendarSlot(start_iso=start_iso, end_iso=slot_end(start_iso, 60)),
                attendees=[cand.get("educator_email", ""), req.get("round2_educator_email", "")],
                description=f"Candidate: {cand.get('educator_name', '')} (event {event_id})",
            )
        except CalendarError as exc:
            data["state"] = "confirm_error"
            data["updated_at"] = _now()
            update_row_by_index(sheets, settings.sheet_round2, idx, data)
            sheets.log(f"round2: calendar create failed for {cand.get('educator_email')}: {exc}", event_id, cand.get("educator_email"))
            continue

        data["state"] = "confirmed"
        data["scheduled_at"] = start_iso
        data["calendar_event_id"] = event_id_out
        data["reminder_at"] = compute_reminder_at(start_iso, 10)
        data["reminded_at"] = ""
        data["updated_at"] = _now()
        update_row_by_index(sheets, settings.sheet_round2, idx, data)

        confirm_msg = (
            f"Confirmed! Your round-2 interview ({req.get('subject')} at {req.get('location')}) "
            f"is on {start_iso}. A confirmation with details has been saved — we'll message you 10 minutes before."
        )
        educator_phone = str(req.get("round2_educator_phone", ""))
        cand_phone = str(cand.get("educator_phone", ""))
        comms.send_whatsapp(cand_phone, confirm_msg, event_id=event_id, email=cand.get("educator_email"))
        comms.send_whatsapp(educator_phone, confirm_msg, event_id=event_id, email=cand.get("educator_email"))
        sheets.log(f"round2 confirmed for {cand.get('educator_email')} on {start_iso}", event_id, cand.get("educator_email"))
        confirmed += 1
    return confirmed


def process_reminders(sheets: SheetsClient, comms: CommsAgent) -> int:
    """Send 10-min-before reminders to candidate + educator, then mark done."""
    _, rows = _all_rows(sheets)
    now = datetime.now(timezone.utc)
    reminded = 0
    for idx, data in rows.items():
        if data.get("state") != "confirmed":
            continue
        if data.get("reminded_at"):
            continue
        reminder_at = data.get("reminder_at", "")
        if not reminder_at:
            continue
        try:
            rem = datetime.fromisoformat(reminder_at)
        except ValueError:
            continue
        if rem.tzinfo is None:
            rem = rem.replace(tzinfo=timezone.utc)
        if rem > now:
            continue
        event_id = data.get("event_id", "")
        cand = _candidate_by_email(sheets, data.get("candidate_email", ""))
        req = get_request(sheets, event_id)
        msg = f"Reminder: your round-2 interview is in 10 minutes ({data.get('scheduled_at')}). See you there!"
        comms.send_whatsapp(str(cand.get("educator_phone", "")), msg, event_id=event_id, email=cand.get("educator_email"))
        comms.send_whatsapp(str(req.get("round2_educator_phone", "")), msg, event_id=event_id)
        data["reminded_at"] = _now()
        data["state"] = "done"
        data["updated_at"] = _now()
        update_row_by_index(sheets, settings.sheet_round2, idx, data)
        reminded += 1
    return reminded