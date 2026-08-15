"""Package the Developer Support handoff for a blocked event.

Usage:
    python -m tools.fix_request --event <event_id>          # print handoff, optionally run sandbox fix
    python -m tools.fix_request --event <event_id> --apply   # run A6 sandbox auto-fix (needs OPENCODE_CLI)
"""
from __future__ import annotations

import argparse
import sys

from config.schema import rows_with
from config.settings import settings
from core.sheets import SheetsClient
from graph.agents.a6_support import build_fix_prompt, run_sandbox_fix


def find_diagnosis_row_index(sheets: SheetsClient, event_id: str) -> tuple[int, dict]:
    rows = rows_with(sheets, settings.sheet_diagnosis, event_id=event_id)
    if not rows:
        raise SystemExit(f"No diagnosis found for event {event_id}")
    return rows[0]


def main() -> int:
    parser = argparse.ArgumentParser(description="Developer Support handoff for a blocked event.")
    parser.add_argument("--event", required=True)
    parser.add_argument("--apply", action="store_true", help="run the sandbox auto-fix")
    args = parser.parse_args()

    sheets = SheetsClient()
    idx, data = find_diagnosis_row_index(sheets, args.event)
    if not settings.opencode_cli and args.apply:
        print("OPENCODE_CLI is not set — cannot auto-run. Printing the handoff prompt instead.")
        args.apply = False

    if args.apply:
        result = run_sandbox_fix(sheets, args.event, idx)
        print(f"Sandbox fix status: {result.get('status')}")
        print(result.get("output", ""))
        return 0

    prompt = build_fix_prompt(sheets, args.event)
    print("=" * 70)
    print("DEVELOPER SUPPORT HANDOFF — give this block to your coding agent:")
    print("=" * 70)
    print(prompt)
    print("=" * 70)
    print("Repro hints: python -m tools.diagnose --event", args.event)
    print("After fixing: run pytest, then python main.py --once. The thread state is checkpointed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())