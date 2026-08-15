"""Startup self-check: verify all integrations before the loop starts.

Usage: python -m tools.healthcheck
Exits 0 when everything is OK, 1 otherwise.
"""
from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from config.settings import settings

REGISTRY: list[tuple[str, callable]] = []


def check(name: str):
    def deco(fn):
        REGISTRY.append((name, fn))
        return fn
    return deco


@check("deepseek key configured")
def _deepseek_key():
    return bool(settings.deepseek_api_key), ("set" if settings.deepseek_api_key else "missing")


@check("gcp service account json path")
def _sa_json():
    from core.auth import decode_info

    raw = settings.gcp_sa_json
    if not raw:
        return False, "missing"
    if Path(raw).exists():
        return True, raw
    try:
        decode_info(raw)
        return True, "inline (base64 or raw JSON)"
    except Exception as exc:  # noqa: BLE001
        return False, f"not a file path or valid JSON: {exc}"


@check("gmail oauth json path (optional)")
def _gmail_json():
    return True, "optional until milestone 3"


@check("sqlite writable")
def _sqlite_writable():
    db = Path(__file__).resolve().parent.parent / ".data"
    db.mkdir(parents=True, exist_ok=True)
    probe = db / "health_probe.db"
    try:
        conn = sqlite3.connect(probe)
        try:
            conn.execute("CREATE TABLE IF NOT EXISTS t (x)")
            conn.execute("INSERT INTO t VALUES (1)")
        finally:
            conn.close()
        probe.unlink()
        return True, "ok"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


@check("tick heartbeat fresh")
def _heartbeat_fresh():
    from config.schema import read_health
    from core.sheets import SheetsClient

    try:
        value = read_health(SheetsClient()).get("last_tick_at", "")
        if not value:
            return False, "no heartbeat recorded yet"
        age = datetime.now(timezone.utc) - datetime.fromisoformat(value)
        stale = age >= timedelta(minutes=settings.heartbeat_stale_minutes)
        return (not stale), f"last tick {age.total_seconds() / 60:.0f} min ago"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


@check("educators sheet readable")
def _educators_readable():
    from core.sheets import SheetsClient

    try:
        SheetsClient().read_range(settings.sheet_educators, "A1:Z1")
        return True, "ok"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


@check("whatsapp sidecar (optional)")
def _wa_sidecar():
    from core.whatsapp_bridge import WhatsAppClient

    try:
        ready = WhatsAppClient().is_ready()
        return True, ("session ready" if ready else "offline (dry-run mode OK)")
    except Exception as exc:  # noqa: BLE001
        return True, f"(check errored: {exc})"


def main() -> int:
    print("Health check:")
    failed = 0
    for name, fn in REGISTRY:
        try:
            result = fn()
        except Exception as exc:  # noqa: BLE001
            ok, detail = False, str(exc)
        else:
            if isinstance(result, tuple):
                ok, detail = bool(result[0]), str(result[1])
            else:
                ok, detail = bool(result), "ok"
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")
        if not ok:
            failed += 1
    print("OK — ready" if failed == 0 else f"{failed} check(s) failed — fix before running the loop")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())