"""Agent 6 — Developer Support.

Triggers only on *blocked* events (circuit breaker tripped). Two steps:
  1. Diagnose (read-only): gather error records + thread context, LLM
     root-cause analysis, write a `Diagnosis` report.
  2. Sandbox auto-fix: if OPENCODE_CLI is configured, run a headless coding
     agent on a git-clean copy of the repo, producing a `Patch` record
     (diff + pytest result). NEVER auto-applies to the live deployment.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.schema import (
    DIAGNOSIS_HEADERS,
    PATCH_HEADERS,
    dict_to_row,
    rows_with,
    update_row_by_index,
)
from config.settings import settings
from core.errors import ErrorRecord, load_error_records
from core.llm import get_chat_model
from core.sheets import SheetsClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# Diagnosis
# --------------------------------------------------------------------------- #
def enqueue_diagnosis(client: SheetsClient, event_id: str, error_type: str, error_message: str) -> None:
    now = _now()
    client.append_row(
        settings.sheet_diagnosis,
        dict_to_row(DIAGNOSIS_HEADERS, {
            "event_id": event_id,
            "status": "queued",
            "error_type": error_type,
            "error_message": error_message[:500],
            "report": "",
            "created_at": now,
            "updated_at": now,
        }),
    )


def build_diagnosis_context(client: SheetsClient, event_id: str) -> dict[str, Any]:
    errors = load_error_records(event_id=event_id, limit=30)
    log_lines = []
    try:
        for _, row in rows_with(client, settings.sheet_log, event_id=event_id):
            log_lines.append(" | ".join(str(row.get(h, "")) for h in ["ts", "level", "source", "message"]))
    except Exception:  # noqa: BLE001
        pass
    return {"event_id": event_id, "errors": errors, "log_lines": log_lines[-50:]}


def diagnose_event(client: SheetsClient, event_id: str, diagnosis_row_index: int) -> dict[str, Any]:
    """Run the LLM root-cause analysis and write the report back."""
    context = build_diagnosis_context(client, event_id)
    report = "error"
    try:
        model = get_chat_model()
        prompt = (
            "You are a developer-support agent. Analyze this hiring-agent failure.\n"
            f"Event: {event_id}\n\n"
            f"Recent ERROR records (JSON):\n{context['errors']}\n\n"
            f"Recent log lines:\n" + ("\n".join(context["log_lines"]) or "(none)")
            + "\n\nReturn a concise structured report with sections: "
            "ROOT_CAUSE, AFFECTED_COMPONENT, SEVERITY (low/medium/high), "
            "SUGGESTED_FIX, SHOULD_AUTO_FIX (yes/no)."
        )
        report = str(model.invoke(prompt).content)
    except Exception as exc:  # noqa: BLE001
        report = f"Diagnosis LLM call failed: {exc}"
    update_row_by_index(client, settings.sheet_diagnosis, diagnosis_row_index, {
        "event_id": event_id,
        "status": "done",
        "report": report,
        "updated_at": _now(),
    })
    return {"status": "done", "report": report}


def process_diagnosis_queue(client: SheetsClient) -> int:
    processed = 0
    for idx, data in rows_with(client, settings.sheet_diagnosis, status="queued"):
        event_id = data.get("event_id", "")
        if not event_id:
            continue
        try:
            diagnose_event(client, event_id, idx)
            processed += 1
        except Exception as exc:  # noqa: BLE001
            update_row_by_index(client, settings.sheet_diagnosis, idx, {"status": "failed", "updated_at": _now()})
            client.log(f"diagnosis failed for {event_id}: {exc}", event_id)
    return processed


# --------------------------------------------------------------------------- #
# Sandbox auto-fix
# --------------------------------------------------------------------------- #
def _copy_repo_to_sandbox() -> Path:
    sandbox = (PROJECT_ROOT / settings.sandbox_dir).resolve()
    if sandbox.exists():
        return sandbox
    ignore = shutil.ignore_patterns(".venv", ".git", ".data", ".sandbox", "logs", "__pycache__", ".pytest_cache")
    shutil.copytree(PROJECT_ROOT, sandbox, ignore=ignore)
    return sandbox


def build_fix_prompt(client: SheetsClient, event_id: str) -> str:
    context = build_diagnosis_context(client, event_id)
    report = ""
    for _, data in rows_with(client, settings.sheet_diagnosis, event_id=event_id):
        report = data.get("report", "")
    return (
        "You are fixing a bug in the educator-hiring-agent repo (current directory).\n"
        f"Event: {event_id}\n\n"
        f"Diagnosis report:\n{report}\n\n"
        f"ERROR records:\n{context['errors']}\n\n"
        "Tasks:\n"
        "1. Reproduce/identify the failing code path.\n"
        "2. Apply a minimal fix.\n"
        "3. Run the test suite: `python -m pytest` (venv at .venv).\n"
        "4. Summarize: FILES_CHANGED, TEST_RESULT, and a short diff-style description."
    )


def run_sandbox_fix(client: SheetsClient, event_id: str, diagnosis_row_index: int) -> dict[str, Any]:
    if not settings.opencode_cli:
        update_row_by_index(client, settings.sheet_diagnosis, diagnosis_row_index, {"status": "manual", "updated_at": _now()})
        return {"status": "manual", "reason": "OPENCODE_CLI not configured"}

    sandbox = _copy_repo_to_sandbox()
    prompt = build_fix_prompt(client, event_id)
    prompt_file = sandbox / "_fix_prompt.txt"
    prompt_file.write_text(prompt, encoding="utf-8")

    now = _now()
    client.append_row(
        settings.sheet_patch,
        dict_to_row(PATCH_HEADERS, {
            "event_id": event_id,
            "diagnosis_id": "",
            "status": "running",
            "diff": "",
            "test_result": "",
            "created_at": now,
            "updated_at": now,
        }),
    )
    try:
        result = subprocess.run(
            [settings.opencode_cli, "run", prompt],
            cwd=str(sandbox),
            capture_output=True,
            text=True,
            timeout=600,
        )
        status = "ready_to_apply" if result.returncode == 0 else "failed"
        return {"status": status, "output": (result.stdout + result.stderr)[-4000:]}
    except subprocess.TimeoutExpired:
        return {"status": "failed", "output": "timeout"}
    except FileNotFoundError:
        return {"status": "manual", "output": f"OPENCODE_CLI not found: {settings.opencode_cli}"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "failed", "output": str(exc)}


def process_sandbox_fixes(client: SheetsClient) -> int:
    """For diagnosis rows marked done + event blocked, attempt a sandbox fix."""
    processed = 0
    for idx, data in rows_with(client, settings.sheet_diagnosis, status="done"):
        event_id = data.get("event_id", "")
        if not event_id:
            continue
        patch = run_sandbox_fix(client, event_id, idx)
        processed += 1
        update_row_by_index(client, settings.sheet_diagnosis, idx, {"status": "fix_attempted", "updated_at": _now()})
        client.log(f"patch for {event_id}: {patch.get('status')} ({patch.get('reason', patch.get('output', ''))[:200]})", event_id)
    return processed