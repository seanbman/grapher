"""Infer component membership edges from path prefixes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from grapher.config import load_config
from grapher.graph import edge_exists, link
from grapher.model import make_edge


def infer_component_links(
    graph: dict[str, Any],
    rules: list[dict[str, str]] | None = None,
    *,
    rel: str = "part_of",
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Link document/artifact nodes to component nodes by path prefix.

    Each rule: {"path_prefix": "src/agent_hub/observability/", "component_id": "comp-observability"}
    """
    nodes = graph.get("nodes") or {}
    proposed: list[dict[str, Any]] = []

    for rule in rules or []:
        prefix = (rule.get("path_prefix") or "").strip()
        comp_id = (rule.get("component_id") or "").strip()
        if not prefix or not comp_id or comp_id not in nodes:
            continue
        for nid, node in nodes.items():
            if nid == comp_id:
                continue
            npath = node.get("path")
            if not npath:
                continue
            try:
                rel_path = Path(npath).as_posix()
            except (TypeError, ValueError):
                rel_path = str(npath)
            if not rel_path.startswith(prefix):
                continue
            if edge_exists(graph, nid, comp_id, rel):
                continue
            proposed.append(
                {
                    "from": nid,
                    "to": comp_id,
                    "rel": rel,
                    "path": rel_path,
                    "title": node.get("title"),
                }
            )
            if not dry_run:
                link(graph, from_id=nid, to_id=comp_id, rel=rel, note="inferred from path prefix")

    return {
        "action": "infer_component_links",
        "dry_run": dry_run,
        "proposed": len(proposed),
        "links": proposed[:50],
    }


def infer_from_config(
    graph: dict[str, Any],
    graph_path: Path,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    cfg = load_config(graph_path)
    rules = cfg.get("component_link_rules") or []
    return infer_component_links(graph, rules, dry_run=dry_run)
