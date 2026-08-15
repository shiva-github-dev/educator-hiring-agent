# Flow — the hiring pipeline

Worked example: **"Physics · JEE · Pune · min 2 yrs"** created on the dashboard.

| # | Step | Who | Result |
|---|------|-----|--------|
| 1 | Request created (fresh / replacement; who's leaving; round-2 interviewer) | A1 | `CentreRequests` row, status `new` |
| 2 | Tick starts the event | A0 | thread `event_id` created |
| 3 | Shortlist: subject overlap + exam + experience filter | A2 | `Candidates` rows (status `queued`) |
| 4 | First WhatsApp outreach (personalized) | A3 | status → `contacted` |
| 5 | No reply → follow-up every 48 h, max 3 | A3 | `follow_up_1..3` |
| 6 | Still nothing after ~1 week | A3 | `no_response` (dropped) |
| 7 | Candidate replies "yes" | A3/inbound | `interested` + ack; joins RTH list |
| 8 | Calendly link sent (knowledge check) | A3 | `kyc_referred` |
| 9 | Checker writes verdict keyed by email | A5 | poll `CheckerVerdicts` |
| 10 | Passed | A5 | `accepted` + acceptance message |
| 11 | Failed | A5 | `rejected` (WhatsApp + email) |
| 12 | Round 2: ask centre educator for slots | A4/A3 | `awaiting_educator_slots` |
| 13 | Educator sends slots → propose to candidate | A4/A3 | `awaiting_candidate_choice` |
| 14 | Candidate picks a slot (or offers an alternative → educator confirms) | A3/inbound | `candidate_chosen` |
| 15 | Google Calendar event created (both invited) | A4 | `confirmed` |
| 16 | Confirmation to both; reminder 10 min before call | A3 | `done` |

## Statuses

**Candidate**: `queued → contacted → follow_up_1..3 → interested → kyc_referred
→ accepted | rejected | no_response | declined → round2_scheduling →
round2_confirmed → hired`

**Round-2** (`Round2` sheet): `awaiting_educator_slots → awaiting_candidate_choice
→ candidate_chosen | awaiting_candidate_alt → confirmed → done`
(plus `confirm_error` when the chosen slot can't be parsed).

**Event**: `new → outreach_in_progress → evaluating → round2 → filled | closed`
(plus `error` when the circuit breaker trips — Agent 6 takes over).

## Failure handling

Every failure → `core/errors.py` (Log sheet + `logs/errors.jsonl`). Node-level
retries on flaky agents; a circuit breaker marks an event `error` after
`EVENT_MAX_FAILURES` and queues a **Diagnosis** for Agent 6, which proposes a
root-cause report and a sandbox-fix patch (never auto-applied). See
`tools/diagnose.py`, `tools/fix_request.py`, `/diagnosis` on the dashboard.
