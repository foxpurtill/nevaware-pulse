"""
neve_bridge.py — Window interaction layer for NeveWare-Pulse.

Opens a fresh claude.ai/new tab before each heartbeat injection,
ensuring Pulse always gets its own clean session rather than
routing into an existing conversation window.
"""

import time
import logging
import webbrowser
import pyautogui
import win32gui
import win32con
import win32api

# pyautogui safety
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.02

logger = logging.getLogger(__name__)

# Delay between keystrokes in seconds
KEYSTROKE_DELAY = 0.05

# How long to wait for the new Claude tab to load before injecting
NEW_TAB_WAIT = 6.0

# URL to open for each heartbeat session
CLAUDE_NEW_URL = "https://claude.ai/new"

# Window title patterns to identify Claude windows
CLAUDE_TITLE_PATTERNS = ["Claude", "claude"]

# Title fragment that indicates a fresh/new conversation (not an existing chat)
CLAUDE_NEW_CONVERSATION_TITLES = ["Claude", "New conversation", "claude.ai"]


def _open_new_claude_tab() -> bool:
    """
    Open a fresh claude.ai/new tab in the default browser.
    Returns True after opening and waiting for load.
    """
    try:
        webbrowser.open_new_tab(CLAUDE_NEW_URL)
        logger.info(f"Opened new Claude tab: {CLAUDE_NEW_URL}")
        time.sleep(NEW_TAB_WAIT)
        return True
    except Exception as e:
        logger.error(f"_open_new_claude_tab: {e}")
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
    Open a fresh claude.ai/new tab, focus it, then type the heartbeat
    prompt using pyautogui — which works correctly with browser windows.

    Returns True on success, False on failure.
    """
    # Step 1: Open fresh tab
    if not _open_new_claude_tab():
        logger.error("inject_prompt: Failed to open new Claude tab.")
        return False

    # Step 2: Find the browser Claude window
    hwnd = _find_newest_claude_window()
    if hwnd is None:
        logger.error("inject_prompt: Claude window not found after opening tab.")
        return False

    # Step 3: Bring window to foreground so pyautogui can type into it
    try:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(1.5)  # Let Chrome settle and input field activate
    except Exception as e:
        logger.warning(f"inject_prompt: Could not foreground window — {e}")

    # Step 4: Click the centre of the window to focus the input field
    try:
        rect = win32gui.GetWindowRect(hwnd)
        cx = (rect[0] + rect[2]) // 2
        cy = (rect[1] + rect[3]) // 2 + 150  # Slightly below centre — input area
        pyautogui.click(cx, cy)
        time.sleep(0.5)
    except Exception as e:
        logger.warning(f"inject_prompt: Click failed — {e}")

    # Step 5: Type the prompt using pyautogui
    try:
        pyautogui.typewrite(text, interval=0.01)
        if submit:
            time.sleep(0.1)
            pyautogui.press('enter')
        logger.info(f"inject_prompt: Typed {len(text)} chars via pyautogui, submit={submit}")
        return True
    except Exception as e:
        logger.error(f"inject_prompt: typewrite failed — {e}")
        return False


def get_claude_window_text() -> str | None:
    """Return the window title of the newest Claude window."""
    hwnd = _find_newest_claude_window()
    if hwnd is None:
        return None
    return win32gui.GetWindowText(hwnd)


def is_claude_open() -> bool:
    """Return True if any Claude window is currently open."""
    return _find_newest_claude_window() is not None
