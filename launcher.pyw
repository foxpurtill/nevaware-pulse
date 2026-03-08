"""
launcher.pyw — Pulse Defibrillator launcher with status popups.

Four states:
  GREEN  — Launched successfully
  RED    — Already running (prevented duplicate)
  AMBER  — Running but Claude app not found
  ERROR  — Failed to launch (with troubleshoot offer)

Run via desktop shortcut. No console window (.pyw extension).
"""

import sys
import os
import subprocess
import tkinter as tk
from tkinter import font as tkfont
import threading
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TRAY_SCRIPT = os.path.join(BASE_DIR, "tray_app.py")

# Claude window title fragments (must match neve_bridge.py)
CLAUDE_TITLE_PATTERNS = ["Claude", "claude"]


# ---------------------------------------------------------------------------
# Process detection
# ---------------------------------------------------------------------------

def is_pulse_running() -> bool:
    """Return True if tray_app.py is already running as a pythonw process."""
    try:
        result = subprocess.run(
            ["powershell", "-Command",
             "Get-WmiObject Win32_Process | Where-Object { $_.CommandLine -like '*tray_app.py*' } | Select-Object -ExpandProperty ProcessId"],
            capture_output=True, text=True, timeout=5
        )
        pids = [l.strip() for l in result.stdout.strip().splitlines() if l.strip().isdigit()]
        return len(pids) > 0
    except Exception:
        return False


def is_claude_running() -> bool:
    """Return True if the Claude desktop app window is visible."""
    try:
        import win32gui
        found = []
        def cb(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if any(p in title for p in CLAUDE_TITLE_PATTERNS):
                    found.append(hwnd)
            return True
        win32gui.EnumWindows(cb, None)
        return len(found) > 0
    except Exception:
        return False


def launch_pulse() -> bool:
    """Launch tray_app.py with pythonw. Returns True on success."""
    try:
        python_exe = sys.executable
        pythonw = os.path.join(os.path.dirname(python_exe), "pythonw.exe")
        if not os.path.exists(pythonw):
            pythonw = python_exe
        subprocess.Popen(
            [pythonw, TRAY_SCRIPT],
            cwd=BASE_DIR,
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        )
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Popup window
# ---------------------------------------------------------------------------

STATES = {
    "launched": {
        "dot": "#44CC66",
        "dot_char": "●",
        "title": "NeveWare's Pulse",
        "title2": "has been Launched!",
        "body": "Heartbeat is active. Red N in your system tray.",
        "button": "OK",
        "alert": False,
    },
    "already_running": {
        "dot": "#FF4444",
        "dot_char": "●",
        "title": "NeveWare's Pulse",
        "title2": "is already running!",
        "body": "Only one instance can run at a time.\nFind the N icon in your system tray.",
        "button": "OK",
        "alert": True,
    },
    "no_claude": {
        "dot": "#FFAA00",
        "dot_char": "●",
        "title": "NeveWare's Pulse IS Running",
        "title2": "but Claude app isn't!",
        "body": "Pulse is active in your tray, but the Claude\ndesktop app isn't open. Heartbeat won't land\nuntil Claude is running.",
        "button": "OK",
        "alert": False,
    },
    "failed": {
        "dot": "⚠",
        "dot_char": "⚠",
        "title": "NeveWare's Pulse",
        "title2": "failed to launch!",
        "body": "Something went wrong starting Pulse.\nWould you like help troubleshooting?",
        "button": "Troubleshoot",
        "alert": True,
    },
}


def show_popup(state_key: str):
    s = STATES[state_key]

    root = tk.Tk()
    root.withdraw()

    win = tk.Toplevel(root)
    win.title("NeveWare-Pulse")
    win.configure(bg="#1a1a2e")
    win.resizable(False, False)
    win.attributes("-topmost", True)

    # Centre on screen
    win.update_idletasks()
    w, h = 360, 200
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    win.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    pad_x = 24
    pad_y = 18

    # Dot / alert symbol
    dot_color = s["dot"] if s["dot_char"] == "●" else "#FFAA00"
    dot_label = tk.Label(
        win,
        text=s["dot_char"],
        fg=dot_color,
        bg="#1a1a2e",
        font=("Segoe UI", 28)
    )
    dot_label.place(x=pad_x, y=pad_y)

    # Title line 1
    tk.Label(
        win,
        text=s["title"],
        fg="#e0e0e0",
        bg="#1a1a2e",
        font=("Segoe UI", 13, "bold"),
        anchor="w"
    ).place(x=pad_x + 44, y=pad_y + 2)

    # Title line 2
    title2_color = "#44CC66" if state_key == "launched" else \
                   "#FF4444" if state_key == "already_running" else \
                   "#FFAA00" if state_key == "no_claude" else "#FF6644"
    tk.Label(
        win,
        text=s["title2"],
        fg=title2_color,
        bg="#1a1a2e",
        font=("Segoe UI", 13, "bold"),
        anchor="w"
    ).place(x=pad_x + 44, y=pad_y + 26)

    # Divider
    tk.Frame(win, bg="#333355", height=1).place(x=pad_x, y=pad_y + 62, width=w - pad_x * 2)

    # Body text
    tk.Label(
        win,
        text=s["body"],
        fg="#aaaacc",
        bg="#1a1a2e",
        font=("Segoe UI", 9),
        justify="left",
        anchor="w"
    ).place(x=pad_x, y=pad_y + 74)

    # Button
    def on_button():
        if state_key == "failed":
            _open_troubleshoot()
        win.destroy()
        root.destroy()

    btn_color = "#FF4444" if s["alert"] else "#3366AA"
    btn = tk.Button(
        win,
        text=s["button"],
        command=on_button,
        bg=btn_color,
        fg="white",
        activebackground="#5588CC",
        activeforeground="white",
        relief="flat",
        font=("Segoe UI", 9, "bold"),
        padx=18,
        pady=6,
        cursor="hand2"
    )
    btn.place(x=w - pad_x - 90, y=h - 50)

    # Auto-close after 6 seconds (except failed state)
    if state_key != "failed":
        def auto_close():
            time.sleep(6)
            try:
                win.destroy()
                root.destroy()
            except Exception:
                pass
        threading.Thread(target=auto_close, daemon=True).start()

    win.protocol("WM_DELETE_WINDOW", lambda: (win.destroy(), root.destroy()))
    root.mainloop()


def _open_troubleshoot():
    """Open a second window with troubleshooting steps."""
    root2 = tk.Tk()
    root2.withdraw()
    win2 = tk.Toplevel(root2)
    win2.title("Pulse Troubleshooter")
    win2.configure(bg="#1a1a2e")
    win2.resizable(False, False)
    win2.attributes("-topmost", True)

    w, h = 420, 280
    sw = win2.winfo_screenwidth()
    sh = win2.winfo_screenheight()
    win2.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    steps = (
        "1.  Check Python is on PATH:\n"
        "       python --version  (in PowerShell)\n\n"
        "2.  Check pywin32 is working:\n"
        "       python -c \"import win32gui; print('OK')\"\n\n"
        "3.  Try launching manually:\n"
        "       pythonw C:\\Code\\nevaware-pulse\\tray_app.py\n\n"
        "4.  Check the log for errors:\n"
        "       C:\\Users\\foxap\\Documents\\Neve\\heartbeat_log.txt"
    )

    tk.Label(
        win2, text="Pulse Troubleshooter", fg="#aaaaff", bg="#1a1a2e",
        font=("Segoe UI", 11, "bold")
    ).pack(pady=(16, 4))

    tk.Label(
        win2, text=steps, fg="#cccccc", bg="#1a1a2e",
        font=("Consolas", 8), justify="left", anchor="w"
    ).pack(padx=20, pady=8, anchor="w")

    tk.Button(
        win2, text="Close", command=lambda: (win2.destroy(), root2.destroy()),
        bg="#333366", fg="white", relief="flat",
        font=("Segoe UI", 9), padx=14, pady=5
    ).pack(pady=8)

    win2.protocol("WM_DELETE_WINDOW", lambda: (win2.destroy(), root2.destroy()))
    root2.mainloop()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if is_pulse_running():
        # Already running — show red warning, don't launch again
        show_popup("already_running")
    else:
        success = launch_pulse()
        if not success:
            show_popup("failed")
        else:
            # Give it 2 seconds to start, then check Claude
            time.sleep(2)
            if not is_claude_running():
                show_popup("no_claude")
            else:
                show_popup("launched")
