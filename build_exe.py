"""
build_exe.py — Build Install.exe via PyInstaller.

Usage:
    python build_exe.py

Requires:
    pip install pyinstaller pillow

Output:
    dist/Install.exe  — standalone installer, no Python required
"""

import subprocess, sys, shutil
from pathlib import Path

BASE_DIR  = Path(__file__).parent.resolve()
ASSETS    = BASE_DIR / "assets"
ICON_PNG  = ASSETS / "neveware_pulse_logo.png"
ICON_ICO  = ASSETS / "neveware_pulse_logo.ico"
DIST_DIR  = BASE_DIR / "dist"
BUILD_DIR = BASE_DIR / "_build"

def make_ico():
    """Convert PNG to ICO for the .exe icon."""
    try:
        from PIL import Image
        img = Image.open(ICON_PNG)
        img.save(ICON_ICO, format="ICO",
                 sizes=[(256,256),(128,128),(64,64),(48,48),(32,32),(16,16)])
        print(f"  ✓  Icon: {ICON_ICO}")
    except Exception as e:
        print(f"  ⚠  Could not create .ico: {e} — using default")
        ICON_ICO_str = None
        return None
    return str(ICON_ICO)

def build():
    print("\nNeveWare-Pulse — Build Install.exe")
    print("=" * 40)

    # Install PyInstaller if needed
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "pyinstaller"],
                   check=True)
    print("  ✓  PyInstaller ready")

    ico = make_ico() or ""

    # Collect all data files to bundle
    datas = [
        (str(ASSETS),                       "assets"),
        (str(BASE_DIR / "requirements.txt"),"." ),
        (str(BASE_DIR / "launcher.pyw"),    "." ),
        (str(BASE_DIR / "tray_app.py"),     "." ),
        (str(BASE_DIR / "heartbeat.py"),    "." ),
        (str(BASE_DIR / "settings_window.py"), "."),
        (str(BASE_DIR / "madlib_window.py"),   "."),
        (str(BASE_DIR / "about_window.py"),    "."),
        (str(BASE_DIR / "defibrillator.bat"),  "."),
    ]

    # Add modules directory
    modules_dir = BASE_DIR / "modules"
    if modules_dir.exists():
        datas.append((str(modules_dir), "modules"))

    add_data_args = []
    for src, dest in datas:
        if Path(src).exists():
            add_data_args += ["--add-data", f"{src};{dest}"]

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--name", "Install",
        "--distpath", str(DIST_DIR),
        "--workpath", str(BUILD_DIR),
        "--specpath", str(BUILD_DIR),
        "--clean",
        *([f"--icon={ico}"] if ico else []),
        *add_data_args,
        "--hidden-import", "pystray._win32",
        "--hidden-import", "PIL._tkinter_finder",
        "--hidden-import", "win32api",
        "--hidden-import", "win32con",
        "--hidden-import", "win32gui",
        "--hidden-import", "keyboard",
        str(BASE_DIR / "install.py"),
    ]

    print("\n  Building... (this takes a minute)\n")
    result = subprocess.run(cmd, cwd=str(BASE_DIR))

    if result.returncode == 0:
        exe = DIST_DIR / "Install.exe"
        size_mb = exe.stat().st_size / 1_048_576
        print(f"\n  ✓  Built: {exe}  ({size_mb:.1f} MB)")
        print(f"\n  Distribute this single file.")
        print(f"  Users double-click Install.exe — no Python needed.\n")
    else:
        print(f"\n  ✗  Build failed. Check output above.\n")
        sys.exit(1)

if __name__ == "__main__":
    build()
