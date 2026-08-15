"""Single-process entry for Docker/Render: tick scheduler (background) + dashboard."""
from __future__ import annotations

import os
from datetime import datetime, timezone

import uvicorn
from apscheduler.schedulers.background import BackgroundScheduler

from config.settings import settings


def _run_once() -> None:
    # Lazy import so the process binds fast on Render (heavy deps load in the
    # scheduler thread instead of blocking startup).
    from scheduler.tick import run_once

    run_once()


def main() -> None:
    scheduler = BackgroundScheduler(timezone="UTC")
    # Fire one tick immediately on boot, then on the interval.
    scheduler.add_job(_run_once, "date", run_date=datetime.now(timezone.utc))
    scheduler.add_job(
        _run_once,
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