"""Install Cursor rules/skills so agents use grapher."""

from __future__ import annotations

import importlib.resources as resources
from pathlib import Path
from typing import Any

from grapher.ingest import project_root_for
from grapher.store import init_store, resolve_graph_path

ASSET_RULE = ("cursor_assets", "rules", "grapher.mdc")
ASSET_SKILL = ("cursor_assets", "skills", "grapher-ingest", "SKILL.md")


def _read_asset(*parts: str) -> str:
    # parts[0] is package-relative root dir name under grapher
    pkg = resources.files("grapher")
    node = pkg.joinpath(*parts)
    return node.read_text(encoding="utf-8")


def _write_file(path: Path, content: str, *, force: bool) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and not force:
        existing = path.read_text(encoding="utf-8")
        if existing == content:
            return "unchanged"
        return "exists"
    path.write_text(content, encoding="utf-8")
    return "written"


def cursor_project_root(graph_path: Path | None = None) -> Path:
    if graph_path is not None:
        return project_root_for(graph_path)
    try:
        return project_root_for(resolve_graph_path(None, create=False))
    except FileNotFoundError:
        return Path.cwd().resolve()


def install_cursor_integration(
    *,
    project_root: Path | None = None,
    graph: str | None = None,
    force: bool = False,
    ensure_init: bool = True,
) -> dict[str, Any]:
    graph_path = resolve_graph_path(graph, create=True)
    if ensure_init:
        init_store(graph_path)

    root = project_root or project_root_for(graph_path)
    rule_path = root / ".cursor" / "rules" / "grapher.mdc"
    skill_path = root / ".cursor" / "skills" / "grapher-ingest" / "SKILL.md"

    rule_text = _read_asset("cursor_assets", "rules", "grapher.mdc")
    skill_text = _read_asset(
        "cursor_assets", "skills", "grapher-ingest", "SKILL.md"
    )

    results = {
        "project_root": str(root),
        "graph": str(graph_path),
        "files": {
            str(rule_path.relative_to(root)): _write_file(
                rule_path, rule_text, force=force
            ),
            str(skill_path.relative_to(root)): _write_file(
                skill_path, skill_text, force=force
            ),
        },
    }
    skipped = [p for p, st in results["files"].items() if st == "exists"]
    if skipped and not force:
        results["hint"] = (
            "some files already exist; re-run with --force to overwrite"
        )
    results["ok"] = True
    results["message"] = (
        "Cursor integration installed. Agents in this project will use grapher "
        "via .cursor/rules and .cursor/skills."
    )
    return results


def cursor_status(
    *,
    project_root: Path | None = None,
    graph: str | None = None,
) -> dict[str, Any]:
    try:
        graph_path = resolve_graph_path(graph, create=False)
        root = project_root or project_root_for(graph_path)
        graph_ok = graph_path.is_file()
    except FileNotFoundError:
        graph_path = None
        root = project_root or Path.cwd().resolve()
        graph_ok = False

    rule_path = root / ".cursor" / "rules" / "grapher.mdc"
    skill_path = root / ".cursor" / "skills" / "grapher-ingest" / "SKILL.md"
    return {
        "project_root": str(root),
        "graph": str(graph_path) if graph_path else None,
        "graph_initialized": graph_ok,
        "rule_installed": rule_path.is_file(),
        "skill_installed": skill_path.is_file(),
        "rule_path": str(rule_path),
        "skill_path": str(skill_path),
        "ready": graph_ok and rule_path.is_file() and skill_path.is_file(),
    }
