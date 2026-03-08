"""
email_watcher.py — Gmail notification and inbox check module for NeveWare-Pulse.

Two functions:
  1. Background thread polls Gmail every N minutes, fires Windows toast on new mail.
  2. get_inbox_summary() — called during heartbeat to give Neve inbox context.

OAuth2 token-based. No passwords stored.
Credentials file: modules/email_watcher/credentials.json (from Google Cloud Console)
Token cache:      modules/email_watcher/token_<address>.json (auto-created on first auth)
"""

import os
import json
import time
import logging
import threading
import webbrowser
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

MODULE_DIR = Path(__file__).parent
CREDENTIALS_FILE = MODULE_DIR / "credentials.json"

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# ----------------------------------------------------------------------------
# Google API helpers
# ----------------------------------------------------------------------------

def _get_service(account_address: str):
    """
    Return an authorised Gmail API service object for the given address.
    On first run, opens a browser for OAuth2 consent.
    Token is cached to token_<address>.json.
    """
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError:
        logger.error("Google API libraries not installed. Run: pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client")
        return None

    token_file = MODULE_DIR / f"token_{account_address.replace('@','_at_')}.json"
    creds = None

    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                logger.error(
                    f"credentials.json not found at {CREDENTIALS_FILE}. "
                    "Download it from Google Cloud Console > APIs & Services > Credentials."
                )
                return None
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)

        with open(token_file, "w") as f:
            f.write(creds.to_json())

    try:
        service = build("gmail", "v1", credentials=creds)
        return service
    except Exception as e:
        logger.error(f"Gmail API build failed: {e}")
        return None


def _get_new_messages(service, last_history_id: str | None) -> tuple[list[dict], str | None]:
    """
    Return (new_messages, latest_history_id).
    On first call (no history_id), just returns the latest historyId with no messages.
    """
    try:
        profile = service.users().getProfile(userId="me").execute()
        current_history_id = profile.get("historyId")

        if last_history_id is None:
            return [], current_history_id

        history = service.users().history().list(
            userId="me",
            startHistoryId=last_history_id,
            historyTypes=["messageAdded"],
            labelId="INBOX"
        ).execute()

        messages = []
        for record in history.get("history", []):
            for added in record.get("messagesAdded", []):
                msg = added.get("message", {})
                msg_id = msg.get("id")
                if msg_id:
                    detail = service.users().messages().get(
                        userId="me", id=msg_id, format="metadata",
                        metadataHeaders=["From","Subject","Date"]
                    ).execute()
                    headers = {h["name"]: h["value"] for h in detail.get("payload", {}).get("headers", [])}
                    messages.append({
                        "id": msg_id,
                        "from": headers.get("From", ""),
                        "subject": headers.get("Subject", "(no subject)"),
                        "date": headers.get("Date", ""),
                        "snippet": detail.get("snippet", ""),
                    })

        return messages, current_history_id

    except Exception as e:
        logger.error(f"_get_new_messages: {e}")
        return [], last_history_id


def _fire_toast(title: str, message: str, url: str = ""):
    """Fire a Windows desktop toast notification."""
    try:
        from plyer import notification
        notification.notify(
            title=title,
            message=message,
            app_name="NeveWare-Pulse",
            timeout=8
        )
    except Exception:
        try:
            from win10toast import ToastNotifier
            toaster = ToastNotifier()
            toaster.show_toast(title, message, duration=8, threaded=True)
        except Exception as e:
            logger.warning(f"Toast notification failed: {e}")


# ----------------------------------------------------------------------------
# Background polling thread
# ----------------------------------------------------------------------------

class EmailWatcher:
    def __init__(self, config: dict):
        self.config = config
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._history_ids: dict[str, str | None] = {}
        self._services: dict = {}
        self._last_messages: list[dict] = []
        self._lock = threading.Lock()
        self._suspended = False  # True when Fox is present (heartbeat paused)

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="email_watcher")
        self._thread.start()
        logger.info("email_watcher: polling started.")

    def stop(self):
        self._stop_event.set()

    def suspend(self):
        """Suspend polling while Fox is present (heartbeat paused / Green mode).
        Toast notifications stop; get_inbox_summary still works if called manually."""
        with self._lock:
            self._suspended = True
        logger.info("email_watcher: polling suspended (Fox present).")

    def resume(self):
        """Resume polling when Fox goes away (heartbeat active / Red mode)."""
        with self._lock:
            self._suspended = False
        logger.info("email_watcher: polling resumed (Fox away).")

    def get_inbox_summary(self) -> str:
        """
        Return a human-readable summary of recent inbox state for heartbeat context.
        """
        with self._lock:
            if not self._last_messages:
                return "Email inbox: no new messages since last check."
            lines = ["Email inbox — new messages:"]
            for m in self._last_messages[-10:]:
                lines.append(f"  From: {m['from']}  |  Subject: {m['subject']}  |  {m['snippet'][:80]}")
            return "\n".join(lines)

    def _run(self):
        accounts = self.config.get("watched_accounts", [])
        poll_interval = self.config.get("poll_interval_minutes", 5) * 60

        # Initialise history IDs (no notification on first pass)
        for acc in accounts:
            addr = acc.get("address", "")
            svc = _get_service(addr)
            self._services[addr] = svc
            if svc:
                _, hid = _get_new_messages(svc, None)
                self._history_ids[addr] = hid

        while not self._stop_event.wait(poll_interval):
            # Skip polling cycle if suspended (Fox is present / heartbeat paused)
            with self._lock:
                if self._suspended:
                    continue
            new_all = []
            for acc in accounts:
                addr = acc.get("address", "")
                label = acc.get("label", addr)
                svc = self._services.get(addr)
                if svc is None:
                    continue
                messages, new_hid = _get_new_messages(svc, self._history_ids.get(addr))
                self._history_ids[addr] = new_hid

                for m in messages:
                    new_all.append(m)
                    if self.config.get("notify_on_new_mail", True):
                        _fire_toast(
                            title=f"New mail ({label})",
                            message=f"{m['from'][:40]}\n{m['subject'][:60]}"
                        )

            if new_all:
                with self._lock:
                    self._last_messages = new_all


# ----------------------------------------------------------------------------
# Module interface (called by tray_app module discovery)
# ----------------------------------------------------------------------------

_watcher: EmailWatcher | None = None


def on_enable(module_config: dict):
    """Called by tray_app when this module is enabled."""
    global _watcher
    _watcher = EmailWatcher(module_config)
    _watcher.start()


def on_disable():
    """Called by tray_app when this module is disabled."""
    global _watcher
    if _watcher:
        _watcher.stop()
        _watcher = None


def get_inbox_summary() -> str:
    if _watcher:
        return _watcher.get_inbox_summary()
    return ""
