#!/usr/bin/env python3
"""Bump [project].version and print the exact release-cut sequence.

Usage:
    python scripts/next_version.py {patch|minor|major}

Rewrites ONLY the `version = "..."` line under [project] in
pyproject.toml (everything else is preserved byte-for-byte), then
prints the copy-paste git sequence for the cut. The script never
touches git itself — the printed commands are executed by the
operator so the cut stays a conscious, reviewable step.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


def _current_version(text: str) -> tuple[int, int, int]:
    m = re.search(r'(?m)^version\s*=\s*"(\d+)\.(\d+)\.(\d+)"', text)
    if not m:
        sys.exit(f"error: no version = \"X.Y.Z\" line found in {PYPROJECT}")
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in ("patch", "minor", "major"):
        sys.exit("usage: next_version.py {patch|minor|major}")
    kind = sys.argv[1]

    text = PYPROJECT.read_text(encoding="utf-8")
    major, minor, patch = _current_version(text)
    old_version = f"{major}.{minor}.{patch}"
    if kind == "patch":
        patch += 1
    elif kind == "minor":
        minor += 1
        patch = 0
    else:
        major += 1
        minor = 0
        patch = 0
    new_version = f"{major}.{minor}.{patch}"

    new_text, count = re.subn(
        r'(?m)^(version\s*=\s*")\d+\.\d+\.\d+(")',
        rf"\g<1>{new_version}\g<2>",
        text,
        count=1,
    )
    if count != 1:
        sys.exit("error: could not rewrite the version line")
    PYPROJECT.write_text(new_text, encoding="utf-8")
    print(f"pyproject.toml: {old_version} -> {new_version} ({kind})")
    print()
    print("Run this to cut the release:")
    print()
    print(f"    git add pyproject.toml")
    print(f'    git commit -m "chore: bump version to {new_version}"')
    print(f"    git tag v{new_version}")
    print(f"    git push && git push origin v{new_version}")


if __name__ == "__main__":
    main()
