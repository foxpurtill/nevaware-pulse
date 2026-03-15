"""
nevaware_pulse.launcher — Entry point for the `nevaware-pulse` CLI command.

When installed via pip, `nevaware-pulse` on the command line runs this.
Locates the installed package data and launches launcher.pyw via pythonw.
"""

import sys
import os
import subprocess
from pathlib import Path


def main():
    """Entry point: locate and launch NeveWare-Pulse."""
    # Find the package root (where assets/ and launcher.pyw live)
    package_dir = Path(__file__).parent
    root = package_dir.parent

    # Try package data layout first, then fall back to development layout
    launcher_candidates = [
        root / "launcher.pyw",
        package_dir / "launcher.pyw",
    ]

    launcher = None
    for candidate in launcher_candidates:
        if candidate.exists():
            launcher = candidate
            break

    if launcher is None:
        print("NeveWare-Pulse: launcher.pyw not found.")
        print(f"Expected it near: {root}")
        print("Try reinstalling: pip install --force-reinstall nevaware-pulse")
        sys.exit(1)

    # Use pythonw on Windows to avoid a console window
    python = Path(sys.executable)
    pythonw = python.with_name("pythonw.exe")
    if not pythonw.exists():
        pythonw = python

    subprocess.Popen(
        [str(pythonw), str(launcher)],
        cwd=str(launcher.parent),
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
    )

    print("NeveWare-Pulse launched. Look for the N icon in your system tray.")


if __name__ == "__main__":
    main()
