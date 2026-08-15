"""Gmail sending via the bot account (OAuth user credential)."""
from __future__ import annotations

from email.message import EmailMessage
from email.utils import formataddr, formatdate

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from config.settings import settings

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


class GmailError(Exception):
    pass


def _creds() -> Credentials:
    oauth_json = settings.gmail_oauth_json
    if not oauth_json:
        raise GmailError("No GMAIL_OAUTH_JSON configured.")
    creds: Credentials | None = None
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(oauth_json, SCOPES)
        creds = flow.run_local_server(port=0)
    return creds


def send_email(to: str, subject: str, body: str, *, from_name: str = "Hiring Assistant") -> str:
    msg = EmailMessage()
    msg["To"] = to
    msg["From"] = formataddr((from_name, settings.gmail_bot_address))
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg.set_content(body)

    service = build("gmail", "v1", credentials=_creds())
    sent = service.users().messages().send(
        userId="me",
        body={"raw": __import__("base64").urlsafe_b64encode(msg.as_bytes()).decode()},
    ).execute()
    return sent.get("id", "")