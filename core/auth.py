"""Service-account credentials from a file path, a base64 env var, or raw JSON.

`GCP_SA_JSON` may be:
  * a filesystem path to a JSON key file, or
  * the base64-encoded contents of the JSON key file (Docker/PaaS friendly).
This keeps secrets out of the repo.
"""
from __future__ import annotations

import base64
import json
import os

from google.auth import load_credentials_from_file
from google.oauth2 import service_account

from config.settings import settings


def decode_info(raw: str) -> dict:
    """Turn a base64 blob or raw JSON string into the key-file dict."""
    s = (raw or "").strip()
    if not s:
        raise ValueError("empty credentials value")
    try:
        info = json.loads(base64.b64decode(s, validate=True))
    except Exception:  # noqa: BLE001
        info = json.loads(s)  # assume raw JSON
    if not isinstance(info, dict) or "type" not in info:
        raise ValueError("credentials do not look like a service-account JSON")
    return info


def service_account_credentials(scopes: list[str], raw: str | None = None):
    """Return google credentials for the service account."""
    raw = raw if raw is not None else settings.gcp_sa_json
    if not raw:
        raise ValueError("No GCP service-account JSON configured (GCP_SA_JSON).")
    if os.path.exists(raw):
        creds, _ = load_credentials_from_file(raw, scopes=scopes)
        return creds
    info = decode_info(raw)
    return service_account.Credentials.from_service_account_info(info, scopes=scopes)