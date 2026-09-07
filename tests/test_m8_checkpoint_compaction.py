from __future__ import annotations

import json
from pathlib import Path

from grapher.checkpoint import create_checkpoint, refresh_checkpoint
from grapher.curate import compact_related
from grapher.graph import add_node
from grapher.model import empty_graph


def test_checkpoint_captures_durable_source_state_and_all_source_edges(tmp_path: Path):
    path = tmp_path / ".grapher" / "knowledge.json"
    graph = empty_graph()
    add_node(graph, id="a", type="finding", title="A", content="alpha", status="current")
    add_node(graph, id="b", type="finding", title="B", content="beta", status="current")

    result = create_checkpoint(graph, path, title="Current state")
    checkpoint_id = result["id"]
    snapshot = json.loads(Path(result["snapshot"]).read_text())

    assert snapshot["node_ids"] == ["a", "b"]
    assert snapshot["nodes"]["a"]["content"] == "alpha"
    assert snapshot["nodes"]["b"]["content"] == "beta"
    assert set(snapshot["source_hashes"]) == {"a", "b"}
    derived = {
        edge["to"]
        for edge in graph["edges"]
        if edge.get("from") == checkpoint_id and edge.get("rel") == "derived_from"
    }
    assert derived == {"a", "b"}


def test_checkpoint_refresh_detects_semantic_drift_from_snapshot_hash(tmp_path: Path):
    path = tmp_path / ".grapher" / "knowledge.json"
    graph = empty_graph()
    add_node(graph, id="source", type="finding", title="State", content="before", status="current")
    result = create_checkpoint(graph, path, title="Current", node_ids=["source"])

    # Deliberately mutate content without touching updated_at: snapshot comparison must
    # detect state drift rather than trusting timestamps alone.
    graph["nodes"]["source"]["content"] = "after"
    preview = refresh_checkpoint(graph, path, result["id"], dry_run=True)

    assert preview["diff"]["changed_sources"] == ["source"]
    assert preview["diff"]["missing_sources"] == []


def test_compaction_preview_refuses_cross_generation_aggregation():
    graph = empty_graph()
    add_node(
        graph,
        id="g1",
        type="finding",
        title="Release state",
        content="generation one",
        status="current",
        scope={"project_id": "grapher", "mission_id": "release", "generation_id": "g1"},
    )
    add_node(
        graph,
        id="g2",
        type="finding",
        title="Release state",
        content="generation two",
        status="current",
        scope={"project_id": "grapher", "mission_id": "release", "generation_id": "g2"},
    )

    preview = compact_related(graph, topic="release state", dry_run=True)

    assert preview["review_only"] is True
    assert preview["blocked"] is True
    assert preview["block_reason"] == "scope_boundary"
    assert preview["proposed_content"] == ""
    assert {item["generation_id"] for item in preview["scope_boundaries"]} == {"g1", "g2"}


def test_compaction_preview_can_summarize_single_generation():
    graph = empty_graph()
    for node_id, content in (("a", "first"), ("b", "second")):
        add_node(
            graph,
            id=node_id,
            type="finding",
            title="Release state",
            content=content,
            status="current",
            scope={"project_id": "grapher", "mission_id": "release", "generation_id": "g2"},
        )

    preview = compact_related(graph, topic="release state", dry_run=True)

    assert preview["blocked"] is False
    assert "first" in preview["proposed_content"]
    assert "second" in preview["proposed_content"]
