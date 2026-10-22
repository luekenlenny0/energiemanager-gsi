#!/usr/bin/env python3
"""Fill GitHub metadata for the Energiemanager GSI HACS repository."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PLACEHOLDER_OWNER = "__GITHUB_OWNER__"
PLACEHOLDER_REPO = "__GITHUB_REPOSITORY__"


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(2)


def main() -> None:
    if len(sys.argv) not in {2, 3}:
        fail("Usage: python prepare_hacs_repo.py <github-user> [repository]")

    owner = sys.argv[1].strip()
    repository = sys.argv[2].strip() if len(sys.argv) == 3 else "energiemanager-gsi"

    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})", owner):
        fail("GitHub user/organization name looks invalid.")

    if not re.fullmatch(r"[A-Za-z0-9._-]+", repository):
        fail("Repository name looks invalid.")

    replacements = {
        PLACEHOLDER_OWNER: owner,
        PLACEHOLDER_REPO: repository,
        "DEIN_GITHUB_NAME": owner,
    }

    files = [
        ROOT / "custom_components" / "power_manager" / "manifest.json",
        ROOT / "README.md",
        ROOT / "HACS_SETUP.md",
    ]

    for path in files:
        text = path.read_text(encoding="utf-8")
        for old, new in replacements.items():
            text = text.replace(old, new)
        path.write_text(text, encoding="utf-8")

    manifest_path = ROOT / "custom_components" / "power_manager" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_base = f"https://github.com/{owner}/{repository}"

    if manifest.get("documentation") != expected_base:
        fail("documentation URL was not generated correctly.")
    if manifest.get("issue_tracker") != expected_base + "/issues":
        fail("issue_tracker URL was not generated correctly.")
    if manifest.get("codeowners") != [f"@{owner}"]:
        fail("codeowners was not generated correctly.")

    leftovers: list[str] = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        if PLACEHOLDER_OWNER in text or PLACEHOLDER_REPO in text or "DEIN_GITHUB_NAME" in text:
            leftovers.append(str(path.relative_to(ROOT)))

    if leftovers:
        fail("Placeholders remain in: " + ", ".join(leftovers))

    print("HACS repository metadata prepared successfully.")
    print(f"Repository: {expected_base}")
    print("Next: run pytest -v, commit, push, and check GitHub Actions.")


if __name__ == "__main__":
    main()
