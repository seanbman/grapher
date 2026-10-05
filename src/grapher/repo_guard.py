"""Repository boundary enforcement for Grapher runtime and Git-shared state."""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path
from typing import Any

MANAGED_IGNORE_START = "# grapher:runtime:start"
MANAGED_IGNORE_END = "# grapher:runtime:end"
BROAD_IGNORE_RULES = {".grapher", ".grapher/", "/.grapher", "/.grapher/"}
SAFE_TRACKED_EXACT = {".grapher/config.json"}
SAFE_TRACKED_PREFIXES = (".grapher/shared/",)

MANAGED_IGNORE_BLOCK = """# grapher:runtime:start
# Grapher local runtime state. Git-safe Grapher state is config.json + shared/**.
.grapher/knowledge.json
.grapher/history.jsonl
.grapher/vectors.json
.grapher/sync-state.json
.grapher/GRAPHER_CONTEXT.md
.grapher/knowledge.*backup*.json
.grapher/.grapher-*.tmp
.grapher/backups/
# grapher:runtime:end
"""

PRE_COMMIT_HOOK = """#!/bin/sh
# grapher:repo-guard:start
set -eu
bad="$(git diff --cached --name-only --diff-filter=ACMR -- .grapher \
  | grep -Ev '^\\.grapher/(config\\.json|shared(/|$))' || true)"
if [ -n "$bad" ]; then
  echo "ERROR: Grapher local runtime state is staged for commit:" >&2
  echo "$bad" >&2
  echo "Only .grapher/config.json and .grapher/shared/** are Git-safe." >&2
  echo "Unstage the runtime files, run 'grapher publish', then stage only the shared publication." >&2
  exit 1
fi
# grapher:repo-guard:end
"""


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        text=True,
        capture_output=True,
        check=False,
    )


def find_git_root(start: Path) -> Path | None:
    probe = _git(start, "rev-parse", "--show-toplevel")
    if probe.returncode != 0:
        return None
    value = probe.stdout.strip()
    return Path(value).resolve() if value else None


def _is_safe_tracked(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return normalized in SAFE_TRACKED_EXACT or normalized.startswith(SAFE_TRACKED_PREFIXES)


def _tracked_grapher_paths(root: Path) -> list[str]:
    result = _git(root, "ls-files", "-z", "--", ".grapher")
    if result.returncode != 0:
        return []
    return sorted(item for item in result.stdout.split("\0") if item)


def _git_hook_path(root: Path) -> Path | None:
    result = _git(root, "rev-parse", "--git-path", "hooks/pre-commit")
    if result.returncode != 0:
        return None
    raw = result.stdout.strip()
    if not raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def ensure_gitignore_policy(root: Path) -> dict[str, Any]:
    path = root / ".gitignore"
    original = path.read_text(encoding="utf-8") if path.exists() else ""
    lines = original.splitlines()
    kept: list[str] = []
    inside_managed = False
    removed_broad = False

    for line in lines:
        stripped = line.strip()
        if stripped == MANAGED_IGNORE_START:
            inside_managed = True
            continue
        if inside_managed:
            if stripped == MANAGED_IGNORE_END:
                inside_managed = False
            continue
        if stripped in BROAD_IGNORE_RULES:
            removed_broad = True
            continue
        kept.append(line)

    while kept and not kept[-1].strip():
        kept.pop()
    body = "\n".join(kept)
    if body:
        body += "\n\n"
    updated = body + MANAGED_IGNORE_BLOCK
    if updated != original:
        path.write_text(updated, encoding="utf-8")

    return {
        "path": str(path),
        "changed": updated != original,
        "removed_broad_grapher_ignore": removed_broad,
    }


def install_pre_commit_guard(root: Path) -> dict[str, Any]:
    hook = _git_hook_path(root)
    if hook is None:
        return {"installed": False, "reason": "git hook path unavailable"}

    if hook.exists():
        current = hook.read_text(encoding="utf-8", errors="replace")
        if "grapher:repo-guard:start" in current:
            return {"installed": True, "managed": True, "changed": False, "path": str(hook)}
        return {
            "installed": False,
            "managed": False,
            "changed": False,
            "reason": "existing pre-commit hook preserved",
            "path": str(hook),
        }

    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text(PRE_COMMIT_HOOK, encoding="utf-8")
    mode = hook.stat().st_mode
    hook.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return {"installed": True, "managed": True, "changed": True, "path": str(hook)}


def repository_guard_status(graph_path: Path) -> dict[str, Any]:
    root = find_git_root(graph_path.parent)
    if root is None:
        return {
            "git_repository": False,
            "clean": True,
            "repository_root": None,
            "tracked_grapher_paths": [],
            "forbidden_tracked": [],
            "safe_tracked": [],
            "pre_commit_guard": {"installed": False, "reason": "not a Git repository"},
        }

    tracked = _tracked_grapher_paths(root)
    forbidden = [path for path in tracked if not _is_safe_tracked(path)]
    hook = _git_hook_path(root)
    hook_state: dict[str, Any] = {"installed": False}
    if hook is not None and hook.exists():
        content = hook.read_text(encoding="utf-8", errors="replace")
        hook_state = {
            "installed": "grapher:repo-guard:start" in content,
            "path": str(hook),
            "managed": "grapher:repo-guard:start" in content,
        }

    return {
        "git_repository": True,
        "clean": not forbidden,
        "repository_root": str(root),
        "tracked_grapher_paths": tracked,
        "forbidden_tracked": forbidden,
        "safe_tracked": [path for path in tracked if _is_safe_tracked(path)],
        "pre_commit_guard": hook_state,
    }


def ensure_repository_guard(graph_path: Path, *, install_hook: bool = True) -> dict[str, Any]:
    root = find_git_root(graph_path.parent)
    if root is None:
        return repository_guard_status(graph_path)

    ignore = ensure_gitignore_policy(root)
    hook = install_pre_commit_guard(root) if install_hook else {"installed": False, "reason": "disabled"}
    status = repository_guard_status(graph_path)
    status["gitignore"] = ignore
    status["pre_commit_setup"] = hook
    return status


def assert_repository_safe(graph_path: Path) -> dict[str, Any]:
    status = repository_guard_status(graph_path)
    forbidden = status.get("forbidden_tracked") or []
    if forbidden:
        listing = "\n".join(f"  - {path}" for path in forbidden)
        raise ValueError(
            "Grapher local runtime state is tracked by Git and cannot be published safely:\n"
            f"{listing}\n"
            "Only .grapher/config.json and .grapher/shared/** are Git-safe. "
            "Remove runtime paths from the index (git rm --cached), then run grapher repo-guard."
        )
    return status
