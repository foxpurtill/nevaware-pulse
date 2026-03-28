"""
neve_bridge.py — Window interaction layer for NeveWare-Pulse.

Opens a fresh claude.ai/new tab before each heartbeat injection,
ensuring Pulse always gets its own clean session rather than
routing into an existing conversation window.
"""

import time
import logging
import win32gui
import win32con
import win32api

# pyautogui removed — using desktop app Ctrl+N approach instead

logger = logging.getLogger(__name__)

# Delay between keystrokes in seconds
KEYSTROKE_DELAY = 0.05

# Window title patterns to identify Claude windows
CLAUDE_TITLE_PATTERNS = ["Claude", "claude"]


def _open_new_claude_conversation(hwnd: int) -> bool:
    """
    Send Ctrl+N to the Claude desktop app to open a new conversation.
    Returns True after sending and waiting for it to load.
    """
    try:
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.3)
        win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
        win32api.keybd_event(ord('N'), 0, 0, 0)
        win32api.keybd_event(ord('N'), 0, win32con.KEYEVENTF_KEYUP, 0)
        win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
        logger.info("Sent Ctrl+N to open new Claude conversation")
        time.sleep(2.0)
        return True
    except Exception as e:
        logger.error(f"_open_new_claude_conversation: {e}")
        return False


def _find_newest_claude_window() -> int | None:
    """
    Find the most recently created Claude window.
    Prefers browser windows (Chrome/Edge/Firefox with claude.ai)
    over the Claude desktop app to ensure fresh tab targeting.
    """
    browser_windows = []
    claude_app_windows = []

    BROWSER_PATTERNS = ["Chrome", "Edge", "Firefox", "Brave", "Opera"]

    def callback(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return True
        title = win32gui.GetWindowText(hwnd)
        if not title:
            return True

        is_claude = any(p in title for p in CLAUDE_TITLE_PATTERNS)
        if not is_claude:
            return True

        is_browser = any(b in title for b in BROWSER_PATTERNS)
        if is_browser:
            browser_windows.append(hwnd)
        else:
            claude_app_windows.append(hwnd)
        return True

    win32gui.EnumWindows(callback, None)

    # Prefer browser window (our fresh tab) over desktop app
    if browser_windows:
        titles = [win32gui.GetWindowText(h) for h in browser_windows]
        logger.debug(f"Found browser Claude windows: {titles}")
        return browser_windows[-1]

    if claude_app_windows:
        titles = [win32gui.GetWindowText(h) for h in claude_app_windows]
        logger.debug(f"Found Claude app windows: {titles}")
        return claude_app_windows[-1]

    logger.warning("No Claude window found.")
    return None


def _ensure_visible(hwnd: int) -> bool:
    """Restore window if minimised. Does not force foreground."""
    placement = win32gui.GetWindowPlacement(hwnd)
    if placement[1] == win32con.SW_SHOWMINIMIZED:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        time.sleep(0.3)
    return True


def _send_text_to_window(hwnd: int, text: str) -> bool:
    """Post WM_CHAR messages for each character to the window."""
    for char in text:
        code = ord(char)
        win32api.PostMessage(hwnd, win32con.WM_CHAR, code, 0)
        time.sleep(KEYSTROKE_DELAY)
    return True


def _send_enter_to_window(hwnd: int) -> bool:
    """Send Return keystroke to the window."""
    vk_return = win32con.VK_RETURN
    scan = win32api.MapVirtualKey(vk_return, 0)
    lparam_down = (scan << 16) | 1
    lparam_up   = (scan << 16) | 0xC0000001
    win32api.PostMessage(hwnd, win32con.WM_KEYDOWN, vk_return, lparam_down)
    time.sleep(KEYSTROKE_DELAY)
    win32api.PostMessage(hwnd, win32con.WM_KEYUP,   vk_return, lparam_up)
    return True


def inject_prompt(text: str, submit: bool = True) -> bool:
    """
    Find the Claude desktop app, open a new conversation with Ctrl+N,
    then inject the heartbeat prompt into that fresh session.
    """
    # Step 1: Find Claude desktop app window
    hwnd = _find_newest_claude_window()
    if hwnd is None:
        logger.error("inject_prompt: Claude window not found.")
        return False

    _ensure_visible(hwnd)

    # Step 2: Open new conversation
    if not _open_new_claude_conversation(hwnd):
        logger.error("inject_prompt: Failed to open new conversation.")
        return False

    # Step 3: Send text via WM_CHAR (works in desktop app)
    prev_fg = win32gui.GetForegroundWindow()
    try:
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.2)

        if not _send_text_to_window(hwnd, text):
            return False

        if submit:
            time.sleep(0.05)
            if not _send_enter_to_window(hwnd):
                return False

        logger.info(f"inject_prompt: Sent {len(text)} chars to new conversation, submit={submit}")
        return True

    except Exception as e:
        logger.error(f"inject_prompt: Exception — {e}")
        return False

    finally:
        if prev_fg and prev_fg != hwnd:
            try:
                win32gui.SetForegroundWindow(prev_fg)
            except Exception:
                pass


def get_claude_window_text() -> str | None:
    """Return the window title of the newest Claude window."""
    hwnd = _find_newest_claude_window()
    if hwnd is None:
        return None
    return win32gui.GetWindowText(hwnd)


def is_claude_open() -> bool:
    """Return True if any Claude window is currently open."""
    return _find_newest_claude_window() is not None
