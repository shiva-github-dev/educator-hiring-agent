# Setup

## Local

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt   # Windows
.venv\Scripts\python -m pip install -r requirements.txt   # macOS/Linux
cp .env.example .env
```

### Demo mode (no external credentials required)

`DEMO_MODE=true` is the default. You still need a Google service-account JSON
(`GCP_SA_JSON`) because Sheets is the data store:

1. Create a Google Cloud project, enable **Google Sheets API**, create a service
   account, download its JSON → put the path in `GCP_SA_JSON`.
2. Create a spreadsheet, note its id → `SPREADSHEET_ID_DEMO`, share it with the
   service-account email (Editor).
3. `DEEPSEEK_API_KEY` for LLM use (verdict parsing / diagnosis) — optional if
   you only run matching + outreach; set it to get the full experience.

Then:

```bash
.venv\Scripts\python -m bootstrap.setup_sheets   # create tabs + headers
.venv\Scripts\python -m bootstrap.seed_demo      # sample educators/centres/request
.venv\Scripts\python -m tools.healthcheck        # verify everything is wired
.venv\Scripts\python main.py --once              # run one tick (advances the demo request)
.venv\Scripts\uvicorn dashboard.app:app --port 8000   # open http://localhost:8000
```

On the dashboard: create a request, then use the **demo reply buttons** to
simulate a candidate replying "yes", the round-2 educator sending slots, etc.
Each tick or `main.py --once` advances the flow. Watch the `Log` tab for the
simulated outbound messages.

### Real mode

Set `DEMO_MODE=false` and provide the real integrations:

- `GMAIL_OAUTH_JSON` + `GMAIL_BOT_ADDRESS` (bot Gmail OAuth consent file),
- `CALENDAR_ID` for round-2 events (service account must have access),
- `WA_DRY_RUN=false` and run the WhatsApp sidecar (below).

## WhatsApp sidecar (real mode)

```bash
cd wa-sidecar
npm install          # downloads puppeteer chromium (~large)
npm start            # prints a QR — scan with the WhatsApp number
```

Session persists in `wa-sidecar/session-data` (git-ignored), so a VM reboot
doesn't require a re-scan. Healthcheck: `curl http://127.0.0.1:3001/status`.

## Tests

```bash
.venv\Scripts\python -m pytest
```
