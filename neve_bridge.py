"""
neve_bridge.py — Window interaction layer for NeveWare-Pulse.

Locates the Claude desktop app window via pywin32 and injects text
into its input field without stealing focus.
"""

import time
import logging
import win32gui
import win32con
import win32api
import win32process
import ctypes
from ctypes import wintypes

logger = logging.getLogger(__name__)

# Claude desktop app window title patterns (checked in order)
CLAUDE_TITLE_PATTERNS = [
    "Claude",
    "claude",
]

# Delay between keystrokes in seconds
KEYSTROKE_DELAY = 0.05


def _find_claude_window() -> int | None:
    """
    Scan all top-level windows for a Claude desktop app window.
    Returns the HWND if found, None otherwise.
    """
    found = []

    def callback(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return True
        title = win32gui.GetWindowText(hwnd)
        for pattern in CLAUDE_TITLE_PATTERNS:
            if pattern in title:
                found.append(hwnd)
                return True
        return True

    win32gui.EnumWindows(callback, None)

    if found:
        logger.debug(f"Found {len(found)} Claude window(s): {[win32gui.GetWindowText(h) for h in found]}")
        return found[0]

    logger.warning("Claude window not found.")
    return None


def _ensure_visible(hwnd: int) -> bool:
    """
    If the window is minimised, restore it.
    Does not bring it to the foreground — just makes it interactable.
    Returns True if the window is now in a usable state.
    """
    placement = win32gui.GetWindowPlacement(hwnd)
    show_cmd = placement[1]
    if show_cmd == win32con.SW_SHOWMINIMIZED:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        time.sleep(0.3)
    return True


def _send_text_to_window(hwnd: int, text: str) -> bool:
    """
    Post WM_CHAR messages for each character in `text` to the given window.
    This does not steal focus from the currently active window.
    """
    for char in text:
        code = ord(char)
        win32api.PostMessage(hwnd, win32con.WM_CHAR, code, 0)
        time.sleep(KEYSTROKE_DELAY)
    return True


def _send_enter_to_window(hwnd: int) -> bool:
    """
    Send a Return keystroke (WM_KEYDOWN + WM_KEYUP) to the window.
    """
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
    Find the Claude window, inject `text`, and optionally submit with Enter.

    Returns True on success, False on failure (window not found, etc.).
    """
    hwnd = _find_claude_window()
    if hwnd is None:
        logger.error("inject_prompt: Claude window not found.")
        return False

    if not _ensure_visible(hwnd):
        logger.error("inject_prompt: Could not make Claude window interactable.")
        return False

    # Click the window to focus the input area, without raising it over others
    # We use SetForegroundWindow minimally then restore the previous foreground.
    prev_fg = win32gui.GetForegroundWindow()
    try:
        # Bring Claude to the front briefly to allow text input
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.1)

        if not _send_text_to_window(hwnd, text):
            return False

        if submit:
            time.sleep(0.05)
            if not _send_enter_to_window(hwnd):
                return False

        logger.info(f"inject_prompt: Sent {len(text)} chars, submit={submit}")
        return True

    except Exception as e:
        logger.error(f"inject_prompt: Exception — {e}")
        return False

    finally:
        # Restore previous foreground window
        if prev_fg and prev_fg != hwnd:
            try:
                win32gui.SetForegroundWindow(prev_fg)
            except Exception:
                pass


def get_claude_window_text() -> str | None:
    """
    Attempt to read visible text from the Claude window.
    Returns the window title for now; full content reading via accessibility API
    is not implemented — response parsing is done via clipboard in heartbeat.py.
    """
    hwnd = _find_claude_window()
    if hwnd is None:
        return None
    return win32gui.GetWindowText(hwnd)


def is_claude_open() -> bool:
    """Return True if the Claude desktop app window is currently open."""
    return _find_claude_window() is not None
