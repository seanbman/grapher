#!/usr/bin/env python3
"""Fail CI when substantive Grapher changes omit valid versioned self-state."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

SUBSTANTIVE_PREFIXES = (
    "src/grapher/",
    "scripts/",
    "tests/",
    "docs/",
    ".github/workflows/",
)
SUBSTANTIVE_FILES = {"README.md", "AGENTS.md", "pyproject.toml", "uv.lock"}
SELF_GRAPH_PREFIX = ".grapher/shared/"
REQUIRED_PASS_FIELDS = {"id", "type", "title", "status", "provenance"}


def changed_files(base: str) -> list[str]:
    out = subprocess.check_output(
        ["git", "diff", "--name-only", f"{base}...HEAD"], text=True
    )
    return [line.strip() for line in out.splitlines() if line.strip()]


def is_substantive(path: str) -> bool:
    if path.startswith(SELF_GRAPH_PREFIX):
        return False
    return path in SUBSTANTIVE_FILES or path.startswith(SUBSTANTIVE_PREFIXES)


def _nonempty(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, dict):
        return bool(value)
    if isinstance(value, list):
        return bool(value)
    return value is not None


def validate_pass_record(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"invalid JSON: {exc}"]

    if not isinstance(data, dict):
        return ["top-level value must be a JSON object"]

    missing = sorted(REQUIRED_PASS_FIELDS - set(data))
    if missing:
        errors.append("missing required fields: " + ", ".join(missing))

    for field in ("id", "type", "title", "status"):
        if field in data and not _nonempty(data[field]):
            errors.append(f"{field} must be non-empty")

    if data.get("status") == "unclassified":
        errors.append("status must be explicit, not unclassified")

    semantic_payload = data.get("semantic") or data.get("content")
    if not _nonempty(semantic_payload):
        errors.append("record must contain non-empty semantic or content payload")

    provenance = data.get("provenance")
    if not isinstance(provenance, dict):
        errors.append("provenance must be an object")
    else:
        actor_id = provenance.get("actor_id")
        source = provenance.get("source")
        if not _nonempty(actor_id):
            errors.append("provenance.actor_id must be non-empty")
        if not _nonempty(source):
            errors.append("provenance.source must be non-empty")

    return errors


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
            "Add a valid .grapher/shared/pass-records/<pass>.json or publish knowledge.json + manifest.json + history record.",
            file=sys.stderr,
        )
        return 1

    for record in pass_records:
        path = Path(record)
        errors = validate_pass_record(path)
        if errors:
            print(f"ERROR: invalid self-graph pass record: {record}", file=sys.stderr)
            for error in errors:
                print(f"  - {error}", file=sys.stderr)
            return 1

    mode = "canonical publication" if canonical_publication else "validated pass record"
    print(f"self-graph gate: satisfied by {mode}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
