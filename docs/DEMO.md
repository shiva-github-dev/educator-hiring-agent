# DEMO — interviewer walkthrough (~5 minutes)

The live instance runs in **demo mode**: no real messages are sent, no real
calendar events are created. Everything is simulated but uses the *real*
pipeline code.

## 1. Look around the repo (2 min)

- `README.md` → architecture diagram, agent map, flow table.
- `docs/FLOW.md` → the full status lifecycle with a worked example.
- `docs/ARCHITECTURE.md` → how A0–A6 fit together and the tick model.
- `tests/` → 50+ tests (matching, inbound, follow-ups, verdicts, round-2,
  error handling) — run them with `python -m pytest`.

## 2. Drive the live server (3 min)

Open the deployed dashboard URL.

1. **Create a request** — Centre `North Centre`, Location `Pune`, Subject
   `Physics`, Exam `JEE`, Min years `2`, Hiring type `Fresh`, pick the round-2
   interviewer. Submit.
2. The request appears as **`new`**. Wait ~15 s (or reload) — the tick
   shortlists matching educators and sends the first outreach (statuses →
   `contacted`). Check the **Candidates** table and the **Log** tab to see the
   simulated WhatsApp messages the agent *would* have sent.
3. **Reply as a candidate** — click **Reply yes** next to a candidate. Status →
   `interested`; the agent acks and (next tick) sends the Calendly link →
   `kyc_referred`.
4. **Play the checker** — append a row to the `CheckerVerdicts` tab for that
   educator's email with `verdict = PASS`. Next tick: status → `accepted` +
   acceptance message. (For the reverse, use `FAIL - not recommended` → rejected
   via WhatsApp + email.)
5. **Round 2** — as the accepted candidate moves on, the agent asks the
   **round-2 educator** for slots. In the *Simulate an inbound message* box,
   reply **as the educator's phone** (from the Requests table) with two slot
   lines:
   ```
   2026-08-20T11:00:00
   2026-08-21T17:30:00
   ```
   Then reply **as the candidate** with `1` to pick the first slot. The agent
   creates a (demo) calendar event and confirms to both.
6. **Errors** — the flow is resilient: check `/healthz` (tick heartbeat), and
   if you break something, the event goes to `error` and appears under
   `Diagnosis` (`/diagnosis`) — the Agent 6 report.
7. `/logs` shows the full event log including every simulated outbound message.

## Try the quick-reply buttons

Each candidate row has **Reply yes / Reply no** buttons — a one-click way to
exercise the outreach → interested → Calendly → verdict path end to end.
