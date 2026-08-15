"""Agent 3 — all outbound communications: WhatsApp + email (no voice)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from config.settings import settings
from core import gmail
from core.whatsapp_bridge import WhatsAppClient, WhatsAppError

TEMPLATES = {
    "outreach": (
        "Hi {name}! We came across your profile as a {subject} educator "
        "({exam} focus, {years} yrs exp). An education centre in {location} is "
        "hiring for this subject. Would you be interested in exploring this "
        "opportunity? Reply 'yes' or 'no'."
    ),
    "follow_up": (
        "Hi {name}, just checking back on the {subject} teaching opportunity "
        "in {location} — still interested? Reply 'yes' or 'no'."
    ),
    "calendly": (
        "Great, {name}! Book a short knowledge check here: {link} "
        "It takes 15 minutes and lets us match you faster."
    ),
    "round2_confirm": (
        "Confirmed! Your interview with the centre's educator is on {slot}. "
        "We'll message you 10 minutes before. Reply if you need to reschedule."
    ),
    "reminder": (
        "Reminder: your {kind} is in 10 minutes. Join link/instructions: {link}"
    ),
    "rejection": (
        "Hi {name}, thanks for your time and effort. After the knowledge check "
        "we've decided not to move forward for this role. We'll keep your "
        "profile for future openings."
    ),
    "accept_round2": (
        "Hi {name}, great news — you cleared the knowledge check! "
        "We'll be in touch shortly to schedule the next round with the centre."
    ),
    "interested_ack": (
        "Great to hear, {name}! Our team is preparing the next step "
        "and we'll share a short knowledge-check link with you shortly."
    ),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def fill(template_key: str, **kwargs: Any) -> str:
    return TEMPLATES[template_key].format(**kwargs)


def classify_reply(text: str, chat_model=None) -> Literal["yes", "no", "unclear"]:
    """Keyword-first reply classification; LLM fallback when ambiguous."""
    t = (text or "").strip().lower()
    if not t:
        return "unclear"
    if (
        t in {"no", "n", "nope", "not interested", "no thanks", "no, thanks", "nah", "skip", "not now"}
        or "not interested" in t
        or "no thanks" in t
        or t.startswith("no ")
    ):
        return "no"
    if t in {"yes", "y", "yeah", "yep", "sure", "interested", "i am interested", "count me in", "ok", "okay", "go ahead"}:
        return "yes"
    if any(w in t for w in ("yes", "yeah", "yep", "sure", "interested", "count me in")):
        return "yes"
    if chat_model is not None:
        resp = chat_model.invoke(
            f"Classify this WhatsApp reply into one of: yes, no, unclear. Reply with exactly one word.\n{text!r}"
        )
        value = (resp.content or "").strip().lower()
        if value.startswith("yes"):
            return "yes"
        if value.startswith("no"):
            return "no"
    return "unclear"


class CommsAgent:
    def __init__(self, wa: WhatsAppClient | None = None, dry_run: bool | None = None, sheets=None) -> None:
        self.wa = wa or WhatsAppClient()
        # Default: honor settings; test scaffolds may pass dry_run explicitly.
        self.dry_run = (settings.demo_mode or settings.wa_dry_run) if dry_run is None else dry_run
        self.sheets = sheets  # when set + dry_run, records the would-be message to the Log sheet

    def _console(self, event_id: str, email: str, line: str) -> None:
        if self.sheets is None:
            return
        try:
            self.sheets.append_row(settings.sheet_log, [_now(), "COMMS", event_id, email, line])
        except Exception:  # noqa: BLE001
            pass

    def send_whatsapp(self, to_number: str, text: str, *, event_id: str = "", email: str = "") -> bool:
        if self.dry_run:
            print(f"[DRY-RUN WA] {to_number}: {text}")
            self._console(event_id, email, f"[WA → {to_number}] {text}")
            return True
        try:
            self.wa.send_text(to_number, text)
            self._console(event_id, email, f"[WA → {to_number}] {text}")
            return True
        except (WhatsAppError, Exception) as exc:  # noqa: BLE001
            print(f"[WA FAILED] {to_number}: {exc}")
            self._console(event_id, email, f"[WA FAILED → {to_number}] {exc}")
            return False

    def send_email(self, to: str, subject: str, body: str, *, event_id: str = "") -> bool:
        if self.dry_run:
            print(f"[DRY-RUN EMAIL] {to}: {subject}")
            self._console(event_id, to, f"[EMAIL → {to}] {subject}: {body[:300]}")
            return True
        try:
            gmail.send_email(to, subject, body)
            self._console(event_id, to, f"[EMAIL → {to}] {subject}")
            return True
        except Exception as exc:  # noqa: BLE001
            print(f"[EMAIL FAILED] {to}: {exc}")
            self._console(event_id, to, f"[EMAIL FAILED → {to}] {exc}")
            return False

    # ---- workflow steps ---------------------------------------------------
    def send_outreach(self, req: dict[str, Any], cand: dict[str, Any]) -> bool:
        text = fill(
            "outreach",
            name=cand.get("educator_name", "there"),
            subject=req.get("subject", ""),
            exam=req.get("exam", ""),
            years=cand.get("years_exp", "?"),
            location=req.get("location", ""),
        )
        return self.send_whatsapp(cand["educator_phone"], text, event_id=req.get("event_id", ""))

    def send_follow_up(self, req: dict[str, Any], cand: dict[str, Any]) -> bool:
        text = fill(
            "follow_up",
            name=cand.get("educator_name", "there"),
            subject=req.get("subject", ""),
            location=req.get("location", ""),
        )
        return self.send_whatsapp(cand["educator_phone"], text, event_id=req.get("event_id", ""))

    def send_calendly(self, cand: dict[str, Any], link: str) -> bool:
        text = fill("calendly", name=cand.get("educator_name", "there"), link=link)
        return self.send_whatsapp(cand["educator_phone"], text, event_id=cand.get("event_id", ""))

    def send_rejection(self, cand: dict[str, Any]) -> tuple[bool, bool]:
        body = fill("rejection", name=cand.get("educator_name", "there"))
        wa_ok = self.send_whatsapp(cand["educator_phone"], body, event_id=cand.get("event_id", ""))
        email_ok = self.send_email(
            cand["educator_email"],
            "Update on your application",
            body,
            event_id=cand.get("event_id", ""),
        )
        return wa_ok, email_ok

    def send_interested_ack(self, cand: dict[str, Any]) -> bool:
        text = fill("interested_ack", name=cand.get("educator_name", "there"))
        return self.send_whatsapp(cand["educator_phone"], text, event_id=cand.get("event_id", ""))
