"""
kill_pulse.pyw — Immediately shut down NeveWare-Pulse and show confirmation.

Can be placed on the Desktop or in the app folder as a companion shortcut.
No console window (.pyw extension).
"""

import subprocess
import sys
import time
import tkinter as tk
from pathlib import Path

BASE_DIR = Path(__file__).parent


def kill_pulse() -> bool:
    """Kill all tray_app.py processes. Returns True if any were killed."""
    try:
        result = subprocess.run(
            ["powershell", "-Command",
             "Get-WmiObject Win32_Process | Where-Object { $_.CommandLine -like '*tray_app.py*' } | Select-Object -ExpandProperty ProcessId"],
            capture_output=True, text=True, timeout=5
        )
        pids = [l.strip() for l in result.stdout.strip().splitlines() if l.strip().isdigit()]
        if not pids:
            return False
        for pid in pids:
            subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True)
        return True
    except Exception:
        return False


def show_result(killed: bool):
    root = tk.Tk()
    root.withdraw()

    win = tk.Toplevel(root)
    win.title("NeveWare-Pulse")
    win.configure(bg="#1a1a2e")
    win.resizable(False, False)
    win.attributes("-topmost", True)

    w, h = 360, 180
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    win.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    dot_color = "#888888" if killed else "#FF4444"
    dot_char = "○" if killed else "●"

    tk.Label(win, text=dot_char, fg=dot_color, bg="#1a1a2e",
             font=("Segoe UI", 20)).place(x=24, y=24)

    if killed:
        title2 = "has been shut down."
        body = "Pulse is no longer running.\nUse the Defibrillator to bring it back."
    else:
        title2 = "was not running."
        body = "No active Pulse process was found."

    tk.Label(win, text="NeveWare's Pulse", fg="white", bg="#1a1a2e",
             font=("Segoe UI", 12, "bold")).place(x=56, y=20)
    tk.Label(win, text=title2, fg="#aaaacc", bg="#1a1a2e",
             font=("Segoe UI", 10)).place(x=56, y=44)

    tk.Frame(win, bg="#2a2a4a", height=1).place(x=24, y=74, width=w - 48)

    tk.Label(win, text=body, fg="#aaaacc", bg="#1a1a2e",
             font=("Segoe UI", 9), justify="left").place(x=24, y=84)

    def close():
        win.destroy()
        root.destroy()

    tk.Button(win, text="OK", command=close,
              bg="#333355", fg="#aaaacc",
              font=("Segoe UI", 9, "bold"),
              padx=18, pady=5, bd=0, cursor="hand2").place(x=w - 80, y=h - 44)

    # Auto-close after 5 seconds
    def auto_close():
        time.sleep(5)
        try:
            win.destroy()
            root.destroy()
        except Exception:
            pass
    import threading
    threading.Thread(target=auto_close, daemon=True).start()

    win.protocol("WM_DELETE_WINDOW", close)
    root.mainloop()


if __name__ == "__main__":
    killed = kill_pulse()
    show_result(killed)
