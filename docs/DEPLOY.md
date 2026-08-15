# Deploy

Recommended: a small VPS (DigitalOcean / Hetzner) + Docker Compose — persistent
disk keeps the SQLite checkpointer and threads alive across restarts, and it
supports switching to real mode later.

## Render (this project's live demo)

Live URL: **https://educator-hiring-agent.onrender.com** (free tier, demo mode).

Deployed via the Render API from the GitHub repo `shiva-github-dev/educator-hiring-agent`
(public, branch `main`, auto-deploy on push). Env vars set at the service:
`GCP_SA_JSON` (base64), `SPREADSHEET_ID`, `DEMO_MODE=true`, `DEEPSEEK_API_KEY`,
`PYTHON_VERSION=3.12.0`. Build `pip install -r requirements.txt`, start
`python serve.py`, health path `/healthz`.

Notes:
- Free instances sleep after ~15 min idle; the first request wakes them in
  ~30–60 s. Add a free [UptimeRobot](https://uptimerobot.com) ping to
  `/healthz` every 5 min to keep it warm.
- Ephemeral disk: checkpoints/logs reset on redeploy; the Google Sheet is the
  source of truth, so hiring state survives.
- `serve.py` runs the heavy langgraph work in a short-lived `scheduler.run_tick`
  subprocess, so the HTTP server stays lean (~55 MB) and Render never OOMs the
  512 MiB free instance; bind is fast (~5 s) so port detection is happy.

## VPS + Docker Compose (recommended for real mode)

```bash
# on the server, once:
apt update && apt install -y docker.io docker-compose-v2 git

git clone https://github.com/<you>/educator-hiring-agent.git
cd educator-hiring-agent
cp .env.example .env          # fill in values
nano .env

docker compose up -d --build
```

- App: `http://<server-ip>:8000`
- Health: `curl http://<server-ip>:8000/healthz`
- Volumes `app-data` + `app-logs` persist checkpoints and `errors.jsonl`.

## Render / Railway (demo-only alternative)

Render (Web Service): connect the GitHub repo, build command
`pip install -r requirements.txt`, start command `python serve.py`, set env vars,
port `8000`. Note: disk is ephemeral — redeploys reset checkpoints (fine for a
demo).

## Real mode (switch off demo)

1. `DEMO_MODE=false`, `WA_DRY_RUN=false`.
2. Add `GMAIL_OAUTH_JSON` (bot Gmail OAuth), `CALENDAR_ID`, real `SPREADSHEET_ID`
   (not the demo one).
3. Run the WhatsApp sidecar: `cd wa-sidecar && npm install && npm start` (scan
   the QR once). Point `WA_SIDECAR_URL` at it. On the VM, run the sidecar under
   `systemd` or the app's `wa-sidecar` profile so it survives reboots.
4. Re-run `python -m bootstrap.setup_sheets` on the real spreadsheet.

## First-launch checklist

- [ ] `python -m tools.healthcheck` passes (creds, sheets readable, heartbeat fresh)
- [ ] `bootstrap.setup_sheets` + `bootstrap.seed_demo` done (demo) 
- [ ] Dashboard reachable; `/healthz` returns `"status":"ok"`
- [ ] A new request is picked up within one tick interval
