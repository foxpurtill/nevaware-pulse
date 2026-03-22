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

# ---------------------------------------------------------------------------
# 1.1.0 — Shared state flag helpers (writes to neveware-pulse/.state.json)
# ---------------------------------------------------------------------------

_STATE_PATH = MODULE_DIR.parent.parent / ".state.json"


def _load_pulse_state() -> dict:
    try:
        import json as _j
        with open(_STATE_PATH, "r", encoding="utf-8") as _f:
            return _j.load(_f)
    except Exception:
        return {"active": True}


def _save_pulse_state(state: dict):
    try:
        import json as _j
        with open(_STATE_PATH, "w", encoding="utf-8") as _f:
            _j.dump(state, _f)
    except Exception as _e:
        logger.warning(f"email_watcher: state save failed: {_e}")


def _add_email_flag(msg: dict, account_label: str):
    """Add an email flag to shared state. Stays until Gmail marks it read."""
    state = _load_pulse_state()
    flags = state.setdefault("pending_flags", {})
    email_flags = flags.setdefault("email", [])
    # Avoid duplicates
    existing_ids = {f.get("id") for f in email_flags}
    if msg["id"] not in existing_ids:
        email_flags.append({
            "id":      msg["id"],
            "from":    msg["from"],
            "subject": msg["subject"],
            "account": account_label,
            "ts":      datetime.datetime.now().strftime("%H:%M"),
        })
        _save_pulse_state(state)


def _clear_read_email_flags(service, account_label: str):
    """Remove any flagged emails that have been read in Gmail."""
    state = _load_pulse_state()
    flags = state.get("pending_flags", {})
    email_flags = flags.get("email", [])
    if not email_flags:
        return
    to_clear = [f for f in email_flags if f.get("account") == account_label]
    if not to_clear:
        return
    remaining = []
    changed = False
    for flag in email_flags:
        if flag.get("account") != account_label:
            remaining.append(flag)
            continue
        try:
            detail = service.users().messages().get(
                userId="me", id=flag["id"], format="minimal"
            ).execute()
            label_ids = detail.get("labelIds", [])
            if "UNREAD" in label_ids:
                remaining.append(flag)  # still unread — keep
            else:
                changed = True  # read — drop
        except Exception:
            remaining.append(flag)  # on error, keep
    if changed:
        state["pending_flags"]["email"] = remaining
        _save_pulse_state(state)




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
    """
    Pulse-style corner toast for new mail — matches voice output style.
    Shows sender + subject in bottom-right, auto-dismisses after 8s.
    Falls back to plyer/win10toast if tkinter subprocess fails.
    """
    import subprocess, sys, tempfile, os

    title_safe   = title.replace("\\", "\\\\").replace('"', '\\"')
    message_safe = message.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " | ")
    url_safe     = url.replace("\\", "\\\\")

    script = (
        "import tkinter as tk\n"
        "root = tk.Tk()\n"
        "root.overrideredirect(True)\n"
        "root.attributes('-topmost', True)\n"
        "root.attributes('-alpha', 0.92)\n"
        "root.configure(bg='#0a1a2a')\n"
        f'tk.Label(root, text="  \u2709  {title_safe}", font=("Segoe UI", 10, "bold"),\n'
        f'         bg="#0a1a2a", fg="#66aaff", padx=12, pady=6).pack(anchor="w")\n'
        f'tk.Label(root, text="  {message_safe}", font=("Segoe UI", 9),\n'
        f'         bg="#0a1a2a", fg="#ccccee", padx=12, pady=2, wraplength=320, justify="left").pack(anchor="w")\n'
        "root.update_idletasks()\n"
        "sw = root.winfo_screenwidth()\n"
        "sh = root.winfo_screenheight()\n"
        "root.geometry(f'+{sw - root.winfo_width() - 24}+{sh - root.winfo_height() - 110}')\n"
        "root.after(8000, root.destroy)\n"
        "root.mainloop()\n"
    )

    try:
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8")
        tmp.write(script)
        tmp.close()
        subprocess.Popen([sys.executable, tmp.name], creationflags=0x08000000)
        return
    except Exception:
        pass

    # Fallback: plyer or win10toast
    try:
        from plyer import notification
        notification.notify(title=title, message=message, app_name="NeveWare-Pulse", timeout=8)
    except Exception:
        try:
            from win10toast import ToastNotifier
            ToastNotifier().show_toast(title, message, duration=8, threaded=True)
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
                    # 1.1.0 — save email flag for next § prompt
                    _add_email_flag(m, label)
                    if self.config.get("notify_on_new_mail", True):
                        _fire_toast(
                            title=f"New mail ({label})",
                            message=f"{m['from'][:40]}\n{m['subject'][:60]}"
                        )

                # 1.1.0 — clear flags for messages that have been read in Gmail
                _clear_read_email_flags(svc, label)

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
