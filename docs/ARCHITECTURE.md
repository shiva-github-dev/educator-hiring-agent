# Architecture

## Agent map

| Agent | Name | Responsibility |
|-------|------|----------------|
| **A1** | Dashboard | Submit hiring requests (fresh / replacement, who's leaving, round-2 interviewer), watch live progress, errors, diagnosis |
| **A0** | Orchestrator | LangGraph supervisor, one checkpointed thread per request; owns scheduling logic (Calendly, slots, Calendar, reminders) |
| **A2** | Shortlist | Match educators (subject + exam JEE/NEET/both + experience), maintain the contact pipeline and the RTH (interested-only) list |
| **A3** | Communications | ALL outbound — WhatsApp (`whatsapp-web.js` sidecar) + Gmail — outreach, follow-ups, confirmations, reminders, rejections |
| **A5** | Test ecosystem | Poll the checker's verdict sheet (keyed by educator email) → pass/fail → accept or reject |
| **A6** | Developer support | On blocked events: read-only LLM diagnosis + sandbox auto-fix (patch + tests), never auto-applied |

```
A1 Web dashboard ──request──► A0 Orchestrator (LangGraph supervisor)
                                 │ per-request thread + tick scheduler
                                 ├──► A2 Shortlist ── contact pipeline + RTH list
                                 ├──► A3 Comms (WhatsApp sidecar + Gmail)
                                 ├──► A5 Test ecosystem (verdict poll)
                                 └──► A6 Developer support (diagnosis + sandbox fix)
            progress / result ─────────────► back to A1
```

## Components

- **`core/`** — integrations: Google Sheets (`sheets.py`), Gmail (`gmail.py`),
  Google Calendar (`calendar.py`), WhatsApp sidecar client
  (`whatsapp_bridge.py`), DeepSeek LLM (`llm.py`), structured error capture
  (`errors.py`).
- **`graph/`** — the A0 LangGraph state machine (`supervisor.py`, `state.py`,
  `matching.py`) with agents A2/A3/A5/A6 as nodes and scheduling utilities.
- **`scheduler/`** — tick scheduler (`tick.py`) plus the sheet-driven workers:
  inbound replies (`inbound.py`), follow-ups (`followups.py`), Calendly
  (`calendly.py`), verdicts (`verdicts.py`), round-2 negotiation (`round2.py`).
- **`dashboard/`** — FastAPI Agent 1 UI + `/logs`, `/diagnosis`, `/healthz`.
- **`tools/`** — `healthcheck.py`, `diagnose.py`, `fix_request.py` (dev loop).
- **`wa-sidecar/`** — Node `whatsapp-web.js` HTTP sidecar for WhatsApp.
- **`bootstrap/`** — `setup_sheets.py` (create tabs), `seed_demo.py` (sample data).

## Long-running flow model

Hiring takes days (follow-ups, waiting on humans). So A0 is not an interactive
session — it's a state machine advanced by a **tick scheduler** every 15 min:

1. Each tick asks "what's due now?" (new requests, follow-ups, verdicts,
   reminders, blocked events).
2. It advances the relevant thread; the SQLite checkpointer makes threads
   durable across restarts.
3. Google Sheets is the human-visible source of truth; every action is logged.

## Demo vs real

- **Demo mode** (`DEMO_MODE=true`, default): dry-run messages recorded to the
  Log sheet, `DemoCalendar` (no real events), a reply simulator on the
  dashboard — fully self-contained, no credentials needed by visitors.
- **Real mode** (`DEMO_MODE=false`): live WhatsApp via the sidecar, real
  Gmail/Calendar; see `docs/DEPLOY.md`.
