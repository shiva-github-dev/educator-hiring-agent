# Sheets schema

One Google Spreadsheet holds the whole system state. `bootstrap/setup_sheets.py`
creates the tabs; Google Form responses feed `Educators`.

| Tab | Purpose | Key columns |
|-----|---------|-------------|
| `Educators` | Form responses (the DB to match against) | name, email, phone, subjects, years_exp, exam, cv_link |
| `Centres` | DB of current educators per centre (round-2 interviewers) | centre, location, educator_name, educator_email, educator_phone, subject, active |
| `CentreRequests` | Hiring events (status per request) | event_id, centre, location, subject, exam, min_experience, hiring_type, leaving_educator, round2_educator_email, round2_educator_phone, status, created_at, updated_at |
| `Candidates` | One row per event×candidate | event_id, educator_email, educator_phone, educator_name, status, followup_count, next_action_at, calendly_link, verdict, round2_slot, calendar_event_id, created_at |
| `CheckerVerdicts` | 3rd-party knowledge-check results (keyed by email) | event_id, email, verdict, created_at |
| `Round2` | Round-2 slot negotiation state machine | event_id, candidate_email, state, slots_json, choice, alt_text, scheduled_at, calendar_event_id, reminder_at, reminded_at, created_at, updated_at |
| `Log` | Event log (incl. dry-run "would send" messages) | timestamp, level, event_id, candidate_email, message |
| `Diagnosis` | Agent 6 root-cause reports | event_id, status, error_type, error_message, report, created_at, updated_at |
| `Patch` | Agent 6 sandbox-fix results | event_id, diagnosis_id, status, diff, test_result, created_at, updated_at |
| `RunState` | Circuit-breaker failure counters | event_id, failure_count, last_error, last_error_ts, status, diagnosis_requested |
| `Health` | Heartbeats (tick freshness, inbox poll cursor) | key, value, updated_at |

`CheckerVerdicts` verdict strings are parsed leniently — "pass"/"cleared"/"recommend"
→ pass; "fail"/"not recommended"/"weak" → fail.
