"""Run exactly one tick in a short-lived subprocess.

The Render free instance has a 512 MiB limit; importing the langgraph stack in
the long-running server would blow that budget. Instead the server spawns this
module, which loads the heavy deps, runs one tick, and exits — reclaiming memory.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _claim_lock() -> Path | None:
    lock_dir = Path(__file__).resolve().parent.parent / ".data"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = lock_dir / "tick.lock"
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return None
    with os.fdopen(fd, "w") as fh:
        fh.write(str(os.getpid()))
    return lock_path


def main() -> None:
    lock = _claim_lock()
    if lock is None:
        print("run_tick: another tick is in progress; skipping", flush=True)
        return
    try:
        from scheduler.tick import run_once

        run_once()
    finally:
        try:
            lock.unlink()
        except OSError:
            pass


if __name__ == "__main__":
    main()
