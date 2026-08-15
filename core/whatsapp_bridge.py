"""HTTP client for the whatsapp-web.js sidecar (Node).

The sidecar keeps the WhatsApp Web session alive on the VM and exposes a
minimal HTTP API. This client is the adapter A3 uses for all WhatsApp I/O.
"""
from __future__ import annotations

from typing import Any

import requests

from config.settings import settings


class WhatsAppError(Exception):
    pass


class WhatsAppClient:
    def __init__(self, base_url: str | None = None) -> None:
        self._base = (base_url or settings.wa_sidecar_url).rstrip("/")

    def send_text(self, to_number: str, text: str) -> Any:
        resp = requests.post(
            f"{self._base}/send",
            json={"to": to_number, "text": text},
            timeout=30,
        )
        if resp.status_code == 503:
            raise WhatsAppError("WhatsApp session not ready")
        resp.raise_for_status()
        return resp.json()

    def qr(self) -> str:
        try:
            resp = requests.get(f"{self._base}/qr", timeout=5)
            resp.raise_for_status()
            return str(resp.json().get("qr", ""))
        except requests.RequestException:
            return ""

    def is_ready(self) -> bool:
        try:
            resp = requests.get(f"{self._base}/status", timeout=5)
            return bool(resp.json().get("ready", False))
        except requests.RequestException:
            return False

    def inbox(self, after: int = 0) -> list[dict[str, Any]]:
        """Return inbound messages newer than `after` (epoch ms)."""
        resp = requests.get(f"{self._base}/inbox", params={"after": after}, timeout=5)
        resp.raise_for_status()
        return resp.json()