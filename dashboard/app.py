"""Agent 1 — minimal web dashboard: submit hiring requests, watch progress."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from config.schema import CENTRE_REQUEST_HEADERS, dict_to_row, read_health, rows_with
from config.settings import settings
from core.sheets import SheetsClient

app = FastAPI(title="Educator Hiring Agent")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def _sheets() -> SheetsClient:
    return SheetsClient()


def load_centres() -> list[dict[str, Any]]:
    rows = _sheets().read_all(settings.sheet_centres)
    return [r for r in rows if str(r.get("active", "true")).strip().lower() != "false"]


def load_requests() -> list[dict[str, Any]]:
    return _sheets().read_all(settings.sheet_centre_requests)


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    centres = load_centres()
    reqs = load_requests()
    candidates = _sheets().read_all(settings.sheet_candidates)
    round2 = _sheets().read_all(settings.sheet_round2)
    needs_attention = [r for r in reqs if r.get("status", "").strip().lower() in {"error", "needs_attention"}]
    last_tick = read_health(_sheets()).get("last_tick_at", "")
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "centres": centres,
            "requests": reqs,
            "candidates": candidates,
            "round2": round2,
            "needs_attention": needs_attention,
            "last_tick": last_tick,
            "stale_ticks": _stale(last_tick),
            "demo_mode": settings.demo_mode,
        },
    )


@app.post("/demo/reply")
def demo_reply(
    from_number: str = Form(...),
    body: str = Form(...),
    redirect: str = Form("/"),
):
    """Demo-mode reply simulator: feeds a message into the real inbound pipeline."""
    from graph.agents.a3_comms import CommsAgent
    from scheduler.inbound import simulate_inbound

    sheets = _sheets()
    simulate_inbound(sheets, CommsAgent(sheets=sheets), from_number, body)
    return RedirectResponse(redirect, status_code=303)


def _stale(last_tick: str) -> bool:
    if not last_tick:
        return True
    try:
        age = datetime.now(timezone.utc) - datetime.fromisoformat(last_tick)
        return age > timedelta(minutes=settings.heartbeat_stale_minutes)
    except ValueError:
        return True


@app.get("/logs", response_class=HTMLResponse)
def logs(request: Request, event: str = ""):
    rows = _sheets().read_all(settings.sheet_log)
    rows = [r for r in rows if not event or r.get("event_id") == event]
    rows.reverse()
    return templates.TemplateResponse("logs.html", {"request": request, "rows": rows, "event": event})


@app.get("/diagnosis", response_class=HTMLResponse)
def diagnosis(request: Request):
    rows = _sheets().read_all(settings.sheet_diagnosis)
    rows.reverse()
    return templates.TemplateResponse("diagnosis.html", {"request": request, "rows": rows})


@app.get("/healthz")
def healthz():
    health: dict[str, Any] = {"status": "ok"}
    try:
        sheets = _sheets()
        health["sheets_reachable"] = True
        health["last_tick_at"] = read_health(sheets).get("last_tick_at", "")
        health["ticks_stale"] = _stale(health["last_tick_at"])
        if health["ticks_stale"]:
            health["status"] = "warning"
    except Exception as exc:  # noqa: BLE001
        health["sheets_reachable"] = False
        health["status"] = "error"
        health["detail"] = str(exc)
    from graph.supervisor import DB_PATH

    health["sqlite_writable"] = _sqlite_ok()
    health["checkpoint_db_present"] = DB_PATH.exists()
    return JSONResponse(health)


def _sqlite_ok() -> bool:
    try:
        import sqlite3

        with sqlite3.connect(":memory:") as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:  # noqa: BLE001
        return False


@app.post("/requests", response_class=HTMLResponse)
def create_request(
    request: Request,
    centre: str = Form(...),
    location: str = Form(...),
    subject: str = Form(...),
    exam: str = Form(...),
    min_experience: float = Form(0),
    hiring_type: str = Form("fresh"),
    leaving_educator: str = Form(""),
    round2_educator: str = Form(""),
):
    now = datetime.now(timezone.utc).isoformat()
    round2_info = _round2_educator(round2_educator)
    row = {
        "event_id": uuid.uuid4().hex[:12],
        "centre": centre,
        "location": location,
        "subject": subject,
        "exam": exam,
        "min_experience": min_experience,
        "hiring_type": hiring_type,
        "leaving_educator": leaving_educator,
        "round2_educator_email": round2_info.get("email", ""),
        "round2_educator_phone": round2_info.get("phone", ""),
        "status": "new",
        "created_at": now,
        "updated_at": now,
    }
    _sheets().append_row(settings.sheet_centre_requests, dict_to_row(CENTRE_REQUEST_HEADERS, row))
    centres = load_centres()
    reqs = load_requests()
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "centres": centres, "requests": reqs},
    )


def _round2_educator(value: str) -> dict[str, str]:
    """Look up email/phone from the Centres sheet for the selected educator."""
    if not value:
        return {}
    for row in load_centres():
        if row.get("educator_email") == value or str(row.get("educator_name", "")) == value:
            return {"email": row.get("educator_email", ""), "phone": row.get("educator_phone", "")}
    return {}