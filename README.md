# Educator Hiring Agent

> An AI agent that takes educator-hiring requests from education centres, matches
> them against an internal educator database (Google Form responses), reaches out
> to shortlisted educators on WhatsApp, runs them through an AI knowledge check,
> and schedules round-2 interviews with the centre's own educator — fully
> orchestrated, resilient, and observable.

**TL;DR** — create a hiring request → the agent shortlists by subject/exam/experience,
messages candidates on WhatsApp (with follow-ups), sends a Calendly link on interest,
reads the checker's verdict, and books the round-2 interview with the centre's educator
on Google Calendar. Every step is logged, error-handled, and visible on a dashboard.

> **Live demo:** https://educator-hiring-agent.onrender.com (demo mode — create a request,
> then reply as a candidate/round-2 educator from the dashboard's reply buttons).
> Free-tier note: the instance sleeps after ~15 min idle; the first visit may take ~30–60 s.

## Architecture

Six cooperating agents, one Python process, driven by a 15-minute tick scheduler:

```
A1 Web dashboard ──request──► A0 Orchestrator (LangGraph supervisor)
                                 │ per-request thread + SQLite checkpointer
                                 ├──► A2 Shortlist ── contact pipeline + RTH list
                                 ├──► A3 Comms (WhatsApp sidecar + Gmail)
                                 ├──► A5 Test ecosystem (verdict poll)
                                 └──► A6 Developer support (diagnosis + sandbox fix)
            progress / result ─────────────► back to A1
```

| Agent | Role |
|-------|------|
| **A1** | Dashboard — submit requests (fresh/replacement, who's leaving, round-2 interviewer), live status |
| **A0** | Orchestrator — LangGraph state machine, one checkpointed thread per request; scheduling logic |
| **A2** | Shortlist — subject + exam (JEE/NEET/both) + experience matching; RTH (interested-only) list |
| **A3** | Communications — all WhatsApp + email: outreach, follow-ups, confirmations, reminders, rejections |
| **A5** | Test ecosystem — polls the checker verdict sheet → accept / reject |
| **A6** | Developer support — on blocked events: LLM diagnosis + sandbox fix (never auto-applied) |

The flow is long-running (follow-ups, humans), so it's an event-driven state machine
advanced by a tick, not an interactive chat. Google Sheets is the source of truth;
the SQLite checkpointer makes threads durable; `core/errors.py` + a circuit breaker +
Agent 6 handle failures. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and
[docs/FLOW.md](docs/FLOW.md).

## Quick start (demo mode — no credentials needed for visitors)

```bash
pip install -r requirements.txt
cp .env.example .env            # set GCP_SA_JSON, SPREADSHEET_ID_DEMO, DEEPSEEK_API_KEY
python -m bootstrap.setup_sheets
python -m bootstrap.seed_demo
python main.py --once           # advance one tick
uvicorn dashboard.app:app --port 8000   # open http://localhost:8000
```

The dashboard includes a **reply simulator** — click *Reply yes* on a candidate,
reply as the round-2 educator with slots, etc. — so the entire pipeline can be
exercised without real WhatsApp. Full walkthrough: [docs/DEMO.md](docs/DEMO.md).

## Repository map

```
core/          Google Sheets · Gmail · Calendar · WhatsApp bridge · LLM · errors
graph/         A0 LangGraph supervisor + agents (A2, A3, A5, A6) + matching
scheduler/     tick + inbound · follow-ups · calendly · verdicts · round-2
dashboard/     FastAPI Agent 1 UI (/logs /diagnosis /healthz)
wa-sidecar/    Node whatsapp-web.js HTTP sidecar
tools/         healthcheck · diagnose · fix_request  (the A6 dev loop)
bootstrap/     setup_sheets · seed_demo
docs/          architecture · flow · setup · demo · sheets · deploy
tests/         50+ tests
```

## Key sheets

`Educators` (form), `Centres`, `CentreRequests`, `Candidates`,
`CheckerVerdicts`, `Round2`, `Log`, plus agent-6 tabs `Diagnosis`, `Patch`,
`RunState`, `Health`. Schema: [docs/SHEETS.md](docs/SHEETS.md).

## Tests & CI

```bash
python -m pytest
```

GitHub Actions runs the suite on every push.

## Roadmap

- [x] M1 — scaffold, A0 supervisor graph, Sheets bridge, matching, tick, dashboard
- [x] M1.5 — error handling, circuit breaker, Agent 6 (diagnosis + sandbox fix)
- [x] M2 — WhatsApp sidecar, A3 real sends, reply intake, follow-ups
- [x] M3 — Calendly on interest; verdict polling → accept/reject
- [x] M4 — round-2 scheduling, Google Calendar, confirmations, reminders
- [x] M5 — demo mode, reply simulator, seeder, Docker deploy, docs, CI

## License

MIT
