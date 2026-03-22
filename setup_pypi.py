"""
setup_pypi.py — One-run PyPI publishing setup for NeveWare-Pulse.

Two modes:
  python setup_pypi.py            — Trusted Publisher (recommended, no token needed)
  python setup_pypi.py --token    — API token mode (fallback)

Trusted Publisher: GitHub Actions authenticates directly to PyPI via OIDC.
No secrets, no rotation, no expiry. Set up once, works forever.
"""

import sys
import webbrowser
import subprocess
import time
from pathlib import Path

REPO      = "foxpurtill/neveware-pulse"
WORKFLOW  = "release.yml"
PACKAGE   = "nevaware-pulse"
BASE      = Path(__file__).parent.resolve()

GREEN  = "\033[92m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

def pr(msg, colour=RESET):
    print(f"{colour}{msg}{RESET}")

def step(n, msg):
    print(f"\n{BOLD}{CYAN}Step {n}.{RESET} {msg}")

def check_gh():
    try:
        r = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True)
        if "foxpurtill" in r.stdout or "neve-summersnow" in r.stdout:
            return True
    except FileNotFoundError:
        pass
    pr("gh CLI not found or not authenticated. Run: gh auth login", YELLOW)
    return False

def trusted_publisher_mode():
    pr(f"\n{BOLD}NeveWare-Pulse — PyPI Trusted Publisher Setup{RESET}")
    pr("──────────────────────────────────────────────")
    pr("This sets up GitHub Actions to publish to PyPI directly.")
    pr("No API token. No secrets. Just a one-time config on PyPI.")

    step(1, "Log into PyPI as the package owner (foxpurtill).")
    pr("   Opening PyPI login...", CYAN)
    time.sleep(1)
    webbrowser.open("https://pypi.org/account/login/")
    input("   Press Enter once you're logged in...")

    step(2, "Add a Trusted Publisher on PyPI.")
    pr("   Opening the PyPI publishing settings...", CYAN)
    time.sleep(1)
    webbrowser.open("https://pypi.org/manage/account/publishing/")

    pr(f"""
   Fill in the form under {BOLD}"Add a new pending publisher"{RESET}:

     PyPI project name : {GREEN}{PACKAGE}{RESET}
     Owner             : {GREEN}foxpurtill{RESET}
     Repository        : {GREEN}neveware-pulse{RESET}
     Workflow filename : {GREEN}{WORKFLOW}{RESET}
     Environment name  : {YELLOW}(leave blank){RESET}

   Click {BOLD}Add{RESET}. That's it — PyPI will now accept publishes
   from the GitHub Actions release workflow with no token needed.
""")
    input("   Press Enter once the publisher is added...")

    step(3, "Verify the package name is available on PyPI.")
    pr("   Opening package page...", CYAN)
    webbrowser.open(f"https://pypi.org/project/{PACKAGE}/")
    pr(f"""
   If the page shows 404, the name is free — your first publish will
   claim it automatically when you run the release workflow.

   If it shows an existing package owned by foxpurtill, you're
   already set up — the workflow will update the existing listing.
""")
    input("   Press Enter to continue...")

    step(4, "Test by triggering a release.")
    pr(f"""
   Run this to trigger a release from the current VERSION:
   {CYAN}python make_release.py{RESET}

   Or trigger from GitHub UI:
   {CYAN}https://github.com/{REPO}/actions/workflows/{WORKFLOW}{RESET}

   First publish will appear at:
   {CYAN}https://pypi.org/project/{PACKAGE}/{RESET}
""")
    pr(f"{GREEN}✓ Trusted Publisher setup complete.{RESET}")


def token_mode():
    pr(f"\n{BOLD}NeveWare-Pulse — PyPI API Token Setup (fallback){RESET}")
    pr("─────────────────────────────────────────────────")
    pr("Use this if Trusted Publisher isn't available for your account.")

    if not check_gh():
        sys.exit(1)

    step(1, "Log into PyPI and generate an API token.")
    pr("   Opening PyPI token settings...", CYAN)
    webbrowser.open("https://pypi.org/manage/account/token/")
    pr("""
   Create a token scoped to:  nevaware-pulse
   (or 'Entire account' if the package doesn't exist yet)

   Copy the token — it starts with pypi-
""")

    token = input("   Paste your PyPI token here: ").strip()
    if not token.startswith("pypi-"):
        pr("That doesn't look like a PyPI token (should start with pypi-). Aborting.", YELLOW)
        sys.exit(1)

    step(2, "Saving token to GitHub secrets...")
    result = subprocess.run(
        ["gh", "secret", "set", "PYPI_API_TOKEN",
         "--body", token,
         "--repo", REPO],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        pr(f"{GREEN}✓ PYPI_API_TOKEN saved to GitHub secrets.{RESET}")
    else:
        pr(f"Failed: {result.stderr}", YELLOW)
        sys.exit(1)

    step(3, "Updating release workflow to use token instead of OIDC...")
    wf_path = BASE / ".github" / "workflows" / "release.yml"
    src = wf_path.read_text(encoding="utf-8")
    old = (
        "      - name: Publish to PyPI (Trusted Publisher / OIDC)\n"
        "        uses: pypa/gh-action-pypi-publish@release/v1\n"
        "        with:\n"
        "          packages-dir: dist/\n"
        "          skip-existing: true"
    )
    new = (
        "      - name: Publish to PyPI (API token)\n"
        "        env:\n"
        "          TWINE_USERNAME: __token__\n"
        "          TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}\n"
        "        run: |\n"
        "          pip install twine\n"
        "          twine upload dist/*.whl --skip-existing"
    )
    if old in src:
        wf_path.write_text(src.replace(old, new), encoding="utf-8")
        subprocess.run(["git", "add", str(wf_path)], cwd=str(BASE))
        subprocess.run(["git", "commit", "-m",
                        "ci: switch release.yml to API token mode for PyPI"],
                       cwd=str(BASE))
        subprocess.run(["git", "push", "origin", "main"], cwd=str(BASE))
        pr(f"{GREEN}✓ Workflow updated and pushed.{RESET}")
    else:
        pr("Workflow already uses token mode or pattern not found — no change needed.", YELLOW)

    pr(f"\n{GREEN}✓ PyPI token setup complete.{RESET}")
    pr(f"   Trigger a release with: python make_release.py")


if __name__ == "__main__":
    if "--token" in sys.argv:
        token_mode()
    else:
        trusted_publisher_mode()
