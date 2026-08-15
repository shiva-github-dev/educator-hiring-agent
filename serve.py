"""Single-process entry for Docker/Render: tick scheduler (background) + dashboard."""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import uvicorn
from apscheduler.schedulers.background import BackgroundScheduler

from config.settings import settings

_BASE_DIR = Path(__file__).resolve().parent


def _run_tick() -> None:
    """Run one tick in a short-lived subprocess so the server process stays lean.

    The heavy langgraph/langchain imports happen only inside the subprocess and
    their memory is reclaimed when it exits (keeps us under Render's 512 MiB).
    """
    subprocess.Popen(
        [sys.executable, "-m", "scheduler.run_tick"],
        cwd=str(_BASE_DIR),
    )


def main() -> None:
    scheduler = BackgroundScheduler(timezone="UTC")
    # Fire one tick immediately on boot, then on the interval.
    scheduler.add_job(_run_tick, "date", run_date=datetime.now(timezone.utc))
    scheduler.add_job(
        _run_tick,
        "interval",
        minutes=settings.tick_interval_minutes,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=60,
    )
    scheduler.start()
    print(f"serve.py: tick every {settings.tick_interval_minutes} min | demo_mode={settings.demo_mode}")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("dashboard.app:app", host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    main()