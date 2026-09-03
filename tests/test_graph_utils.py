"""Graph utility tests."""

from __future__ import annotations

import json
from pathlib import Path

from grapher.graph import dedupe_edges, edge_exists, link

FIXTURES = Path(__file__).parent / "fixtures"


def test_dedupe_edges_removes_duplicates():
    graph = {
        "nodes": {"a": {"id": "a"}, "b": {"id": "b"}},
        "edges": [
            {"from": "a", "to": "b", "rel": "related"},
            {"from": "a", "to": "b", "rel": "related"},
            {"from": "b", "to": "a", "rel": "references"},
        ],
    }
    removed = dedupe_edges(graph)
    assert removed == 1
    assert len(graph["edges"]) == 2


def test_link_idempotent():
    graph = json.loads((FIXTURES / "museum-exhibit.json").read_text(encoding="utf-8"))
    nids = list(graph["nodes"].keys())
    if len(nids) < 2:
        return
    a, b = nids[0], nids[1]
    before = len(graph["edges"])
    link(graph, from_id=a, to_id=b, rel="related", note="test")
    link(graph, from_id=a, to_id=b, rel="related", note="test again")
    assert len(graph["edges"]) == before + 1
    assert edge_exists(graph, a, b, "related")
