#!/usr/bin/env python3
"""Fail CI when a strict graph contains unapproved unclassified authored nodes."""

from __future__ import annotations

import argparse
from pathlib import Path

from grapher.config import load_config
from grapher.store import load_graph
from grapher.truth_policy import unclassified_authored_node_ids


def _config_anchor(graph_path: Path) -> Path:
    """Resolve project config for working or published shared graph paths."""
    if graph_path.parent.name == "shared" and (graph_path.parent.parent / "config.json").is_file():
        return graph_path.parent.parent / "knowledge.json"
    return graph_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("graph", type=Path)
    args = parser.parse_args()

    graph_path = args.graph.expanduser().resolve()
    config = load_config(_config_anchor(graph_path))
    if not config.get("require_explicit_status", False):
        print("truth-status policy disabled")
        return 0

    graph = load_graph(graph_path)
    legacy = set(config.get("truth_status_legacy_allowlist") or [])
    bad = unclassified_authored_node_ids(graph, legacy_allowlist=legacy)
    if bad:
        print("unclassified authored nodes are forbidden under require_explicit_status=true:")
        for node_id in bad:
            print(f"- {node_id}")
        return 1

    outstanding = sorted(
        node_id
        for node_id in legacy
        if node_id in (graph.get("nodes") or {})
        and str(graph["nodes"][node_id].get("status") or "unclassified") == "unclassified"
    )
    print(f"truth-status policy passed; legacy review queue: {len(outstanding)}")
    for node_id in outstanding:
        print(f"- review: {node_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
