"""Application entrypoint: single tick (--once) or the APScheduler loop."""
from __future__ import annotations

import argparse

from apscheduler.schedulers.blocking import BlockingScheduler

from config.settings import settings
from scheduler.tick import run_once


def _loop() -> None:
    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(run_once, "interval", minutes=settings.tick_interval_minutes, max_instances=1)
    print(f"Tick scheduler starting: every {settings.tick_interval_minutes} min. Ctrl+C to stop.")
    scheduler.start()


def main() -> None:
    parser = argparse.ArgumentParser(description="Educator Hiring Agent — A0 tick scheduler")
    parser.add_argument("--once", action="store_true", help="run a single tick and exit")
    args = parser.parse_args()
    if args.once:
        run_once()
    else:
        _loop()


if __name__ == "__main__":
    main()