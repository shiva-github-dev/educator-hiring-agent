"""Central configuration loaded from environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    deepseek_api_key: str = field(default_factory=lambda: os.getenv("DEEPSEEK_API_KEY", ""))
    deepseek_base_url: str = field(default_factory=lambda: os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"))
    deepseek_model: str = field(default_factory=lambda: os.getenv("DEEPSEEK_MODEL", "deepseek-chat"))

    gcp_sa_json: str = field(default_factory=lambda: os.getenv("GCP_SA_JSON", ""))

    spreadsheet_id: str = field(default_factory=lambda: os.getenv("SPREADSHEET_ID", ""))
    spreadsheet_id_demo: str = field(default_factory=lambda: os.getenv("SPREADSHEET_ID_DEMO", ""))
    demo_mode: bool = field(default_factory=lambda: os.getenv("DEMO_MODE", "true").lower() == "true")
    sheet_educators: str = field(default_factory=lambda: os.getenv("SHEET_EDUCATORS", "Educators"))
    sheet_centres: str = field(default_factory=lambda: os.getenv("SHEET_CENTRES", "Centres"))
    sheet_centre_requests: str = field(default_factory=lambda: os.getenv("SHEET_CENTRE_REQUESTS", "CentreRequests"))
    sheet_candidates: str = field(default_factory=lambda: os.getenv("SHEET_CANDIDATES", "Candidates"))
    sheet_checker_verdicts: str = field(default_factory=lambda: os.getenv("SHEET_CHECKER_VERDICTS", "CheckerVerdicts"))
    sheet_log: str = field(default_factory=lambda: os.getenv("SHEET_LOG", "Log"))
    sheet_diagnosis: str = field(default_factory=lambda: os.getenv("SHEET_DIAGNOSIS", "Diagnosis"))
    sheet_patch: str = field(default_factory=lambda: os.getenv("SHEET_PATCH", "Patch"))
    sheet_run_state: str = field(default_factory=lambda: os.getenv("SHEET_RUN_STATE", "RunState"))
    sheet_health: str = field(default_factory=lambda: os.getenv("SHEET_HEALTH", "Health"))
    sheet_round2: str = field(default_factory=lambda: os.getenv("SHEET_ROUND2", "Round2"))
    calendar_id: str = field(default_factory=lambda: os.getenv("CALENDAR_ID", "primary"))

    gmail_oauth_json: str = field(default_factory=lambda: os.getenv("GMAIL_OAUTH_JSON", ""))
    gmail_bot_address: str = field(default_factory=lambda: os.getenv("GMAIL_BOT_ADDRESS", ""))

    wa_sidecar_url: str = field(default_factory=lambda: os.getenv("WA_SIDECAR_URL", "http://127.0.0.1:3001"))
    wa_dry_run: bool = field(default_factory=lambda: os.getenv("WA_DRY_RUN", "true").lower() == "true")
    calendly_base: str = field(default_factory=lambda: os.getenv("CALENDLY_BASE_URL", "https://calendly.com/your-hiring/15min"))

    # Operational knobs
    follow_up_interval_hours: int = 48
    follow_up_max: int = 3
    drop_after_hours: int = 24 * 7
    tick_interval_minutes: int = 15
    event_max_failures: int = 3
    heartbeat_stale_minutes: int = 30
    logs_dir: str = field(default_factory=lambda: os.getenv("LOGS_DIR", "logs"))
    sandbox_dir: str = field(default_factory=lambda: os.getenv("SANDBOX_DIR", ".sandbox"))
    opencode_cli: str = field(default_factory=lambda: os.getenv("OPENCODE_CLI", ""))


settings = Settings()
