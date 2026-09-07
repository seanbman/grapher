#!/usr/bin/env python3
"""Fail CI when substantive Grapher changes omit a versioned self-graph record."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

SUBSTANTIVE_PREFIXES = (
    "src/grapher/",
    "scripts/",
    "tests/",
    "docs/",
    ".github/workflows/",
)
SUBSTANTIVE_FILES = {"README.md", "AGENTS.md", "pyproject.toml", "uv.lock"}
SELF_GRAPH_PREFIX = ".grapher/shared/"


def changed_files(base: str) -> list[str]:
    out = subprocess.check_output(
        ["git", "diff", "--name-only", f"{base}...HEAD"], text=True
    )
    return [line.strip() for line in out.splitlines() if line.strip()]


def is_substantive(path: str) -> bool:
    if path.startswith(SELF_GRAPH_PREFIX):
        return False
    return path in SUBSTANTIVE_FILES or path.startswith(SUBSTANTIVE_PREFIXES)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True, help="base commit SHA/ref")
    args = parser.parse_args()

    files = changed_files(args.base)
    substantive = sorted(path for path in files if is_substantive(path))
    if not substantive:
        print("self-graph gate: no substantive Grapher changes")
        return 0

    shared_changes = sorted(path for path in files if path.startswith(SELF_GRAPH_PREFIX))
    if not shared_changes:
        print("ERROR: substantive Grapher changes require an update under .grapher/shared/", file=sys.stderr)
        print("Substantive changes:", file=sys.stderr)
        for path in substantive:
            print(f"  - {path}", file=sys.stderr)
        return 1

    pass_records = [
        path for path in shared_changes
        if path.startswith(".grapher/shared/pass-records/") and path.endswith(".json")
    ]
    canonical_publication = {
        ".grapher/shared/knowledge.json",
        ".grapher/shared/manifest.json",
    }.issubset(shared_changes) and any(
        path.startswith(".grapher/shared/history/") and path.endswith(".json")
        for path in shared_changes
    )

    if not pass_records and not canonical_publication:
        print(
            "ERROR: .grapher/shared changed, but no pass record or complete canonical publication was found.",
            file=sys.stderr,
        )
        print(
            "Add .grapher/shared/pass-records/<pass>.json or publish knowledge.json + manifest.json + history record.",
            file=sys.stderr,
        )
        return 1

    for record in pass_records:
        path = Path(record)
        if not path.is_file() or path.stat().st_size < 40:
            print(f"ERROR: invalid self-graph pass record: {record}", file=sys.stderr)
            return 1

    mode = "canonical publication" if canonical_publication else "pass record"
    print(f"self-graph gate: satisfied by {mode}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
