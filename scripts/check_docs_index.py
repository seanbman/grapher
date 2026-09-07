#!/usr/bin/env python3
"""Ensure human-facing docs remain discoverable from docs/INDEX.md."""

from __future__ import annotations

import re
import sys
from pathlib import Path

DOC_ROOT = Path("docs")
INDEX = DOC_ROOT / "INDEX.md"
TRACKED_SUFFIXES = {".md", ".pdf", ".txt"}
EXCLUDED_DIRS = {"grapher"}


def main() -> int:
    if not INDEX.is_file():
        print("ERROR: docs/INDEX.md is required", file=sys.stderr)
        return 1

    index_text = INDEX.read_text(encoding="utf-8")
    missing: list[str] = []
    for path in sorted(DOC_ROOT.rglob("*")):
        if not path.is_file() or path == INDEX or path.suffix.lower() not in TRACKED_SUFFIXES:
            continue
        if any(part in EXCLUDED_DIRS for part in path.relative_to(DOC_ROOT).parts[:-1]):
            continue
        rel = path.relative_to(DOC_ROOT).as_posix()
        if rel not in index_text:
            missing.append(rel)

    if missing:
        print("ERROR: documentation files missing from docs/INDEX.md:", file=sys.stderr)
        for rel in missing:
            print(f"  - {rel}", file=sys.stderr)
        return 1

    architecture = DOC_ROOT / "ARCHITECTURE.md"
    procedures = DOC_ROOT / "PROCEDURES.md"
    for required in (architecture, procedures):
        if not required.is_file():
            print(f"ERROR: required documentation missing: {required}", file=sys.stderr)
            return 1
        text = required.read_text(encoding="utf-8")
        if "```mermaid" not in text:
            print(f"ERROR: {required} must contain a Mermaid diagram", file=sys.stderr)
            return 1
        if not re.search(r"[0-9a-f]{7,40}", text):
            print(f"ERROR: {required} must include commit anchors", file=sys.stderr)
            return 1

    print("documentation index gate: satisfied")
    return 0


if __name__ == "__main__":
    sys.exit(main())
