"""
make_release.py — Trigger a NeveWare-Pulse release from the command line.

Usage:
    python make_release.py              # release current VERSION
    python make_release.py 1.2.0        # release a specific version
    python make_release.py --local      # build wheel locally only (no push)

What it does:
    1. Reads (or sets) the version in VERSION file
    2. Builds the wheel locally
    3. Triggers the GitHub Actions release workflow via `gh workflow run`
       (which builds, creates the GH Release, and uploads to PyPI)

Requirements: gh CLI installed and authenticated (gh auth login)
"""

import sys
import subprocess
import re
from pathlib import Path

BASE = Path(__file__).parent.resolve()
VERSION_FILE = BASE / "VERSION"


def current_version():
    return VERSION_FILE.read_text(encoding="utf-8").strip()


def set_version(v: str):
    VERSION_FILE.write_text(v + "\n", encoding="utf-8")
    print(f"  VERSION set to {v}")


def valid_semver(v: str) -> bool:
    return bool(re.match(r'^\d+\.\d+\.\d+$', v))


def run(cmd, **kwargs):
    print(f"  > {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(BASE), **kwargs)
    if result.returncode != 0:
        print(f"  ERROR: exit {result.returncode}")
        sys.exit(result.returncode)
    return result


def main():
    local_only = "--local" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]

    version = args[0] if args else current_version()

    if not valid_semver(version):
        print(f"Invalid version: {version}  (expected X.Y.Z)")
        sys.exit(1)

    print(f"\nNeveWare-Pulse Release Tool")
    print(f"Version : {version}")
    print(f"Mode    : {'local build only' if local_only else 'full release (GH Actions)'}\n")

    # Optionally update VERSION if an explicit version was supplied
    if args and args[0] != current_version():
        print(f"Updating VERSION: {current_version()} -> {version}")
        set_version(version)
        run(["git", "add", "VERSION"])
        run(["git", "commit", "-m", f"chore: bump version to {version} [skip ci]"])
        run(["git", "push", "origin", "main"])

    # Build wheel locally
    print("\nBuilding wheel...")
    dist = BASE / "dist"
    dist.mkdir(exist_ok=True)
    for old in dist.glob("*.whl"):
        old.unlink()
    run(["python", "-m", "build", "--wheel", "--outdir", str(dist)])
    wheels = list(dist.glob("*.whl"))
    if not wheels:
        print("Build failed — no wheel produced.")
        sys.exit(1)
    print(f"  Built: {wheels[0].name}")

    if local_only:
        print(f"\nDone (local). Wheel at: {wheels[0]}")
        return

    # Trigger GitHub Actions release workflow
    print("\nTriggering GitHub Actions release workflow...")
    run([
        "gh", "workflow", "run", "release.yml",
        "--repo", "foxpurtill/neveware-pulse",
        "--ref", "main",
        "--field", f"version_override={version}",
    ])

    print(f"\nRelease triggered for v{version}.")
    print("Track progress: https://github.com/foxpurtill/neveware-pulse/actions")
    print(f"Release page  : https://github.com/foxpurtill/neveware-pulse/releases/tag/v{version}")


if __name__ == "__main__":
    main()
