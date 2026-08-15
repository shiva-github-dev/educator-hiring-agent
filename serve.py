"""Single-process entry for Docker: tick scheduler (background) + dashboard."""
from __future__ import annotations

import uvicorn
from apscheduler.schedulers.background import BackgroundScheduler

from config.settings import settings
from scheduler.tick import run_once


def main() -> None:
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        run_once,
        "interval",
        minutes=settings.tick_interval_minutes,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=60,
    )
    scheduler.start()
    print(f"serve.py: tick every {settings.tick_interval_minutes} min | demo_mode={settings.demo_mode}")
    uvicorn.run("dashboard.app:app", host="0.0.0.0", port=8000, log_level="info")


if __name__ == "__main__":
    main()