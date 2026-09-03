"""Integration helpers for agent-hub and similar consumers."""

import json
from pathlib import Path

import pytest

from grapher.integrations import agent_hub as GH
from grapher.linking import infer_component_links
from grapher.relation_aliases import alias_relations
from grapher.store import init_store, load_graph, save_graph


@pytest.fixture
def graph_dir(tmp_path: Path) -> Path:
    graph_path = tmp_path / ".grapher" / "knowledge.json"
    init_store(graph_path, name="test", domain="software", profile="software")
    return graph_path


def _history_entries(graph_path: Path) -> list[dict]:
    history = graph_path.parent / "history.jsonl"
    return [json.loads(line) for line in history.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_query_context_uses_graph_path(graph_dir: Path, monkeypatch):
    graph = load_graph(graph_dir)
    GH.contribute_context(
        graph_dir,
        type="finding",
        title="Sparse orphans",
        content="link components after ingest",
        tags=["feedback"],
    )

    calls: list[tuple] = []

    def fake_search(graph, graph_path, query, **kwargs):
        calls.append((graph_path, query, kwargs.get("exclude_superseded")))
        return [{"node": {"id": "x", "title": query}, "score": 1.0}]

    monkeypatch.setattr("grapher.integrations.agent_hub.S.search", fake_search)
    hits = GH.query_context(graph_dir, "orphans")
    assert hits
    assert calls[0][0] == graph_dir
    assert calls[0][1] == "orphans"
    assert calls[0][2] is True


def test_infer_component_links(graph_dir: Path):
    graph = load_graph(graph_dir)
    graph["nodes"]["comp-obs"] = {
        "id": "comp-obs",
        "type": "component",
        "title": "Observability",
        "content": "",
        "tags": [],
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
    }
    graph["nodes"]["doc-1"] = {
        "id": "doc-1",
        "type": "document",
        "title": "observer.py",
        "content": "",
        "path": "src/agent_hub/observability/observer.py",
        "tags": [],
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
    }
    rules = [
        {
            "path_prefix": "src/agent_hub/observability/",
            "component_id": "comp-obs",
        }
    ]
    result = infer_component_links(graph, rules, dry_run=False)
    assert result["proposed"] == 1
    rels = [e for e in graph["edges"] if e["from"] == "doc-1"]
    assert rels and rels[0]["rel"] == "part_of"


def test_alias_relations():
    graph = {
        "nodes": {},
        "edges": [
            {"from": "a", "to": "b", "rel": "informs"},
            {"from": "c", "to": "d", "rel": "implements"},
        ],
    }
    result = alias_relations(graph, dry_run=False)
    assert result["count"] == 1
    assert graph["edges"][0]["rel"] == "references"


def test_get_neighbors_and_infer_links_context(graph_dir: Path):
    GH.contribute_context(
        graph_dir,
        type="component",
        title="Observability",
        content="",
        node_id="comp-obs",
    )
    GH.contribute_context(
        graph_dir,
        type="document",
        title="observer.py",
        content="observer module",
        node_id="doc-1",
        path="src/agent_hub/observability/observer.py",
    )
    detail = GH.get_context(graph_dir, "doc-1")
    assert detail["node"]["id"] == "doc-1"
    hood = GH.neighbors_context(graph_dir, "doc-1", depth=1)
    assert "doc-1" in hood["nodes"]

    cfg_path = graph_dir.parent / "config.json"
    cfg_path.write_text(
        '{"component_link_rules":[{"path_prefix":"src/agent_hub/observability/","component_id":"comp-obs"}]}\n',
        encoding="utf-8",
    )
    result = GH.infer_links_context(graph_dir)
    assert result["proposed"] == 1


def test_contribute_context_preserves_originating_actor_and_create_update_labels(graph_dir: Path):
    provenance = {
        "actor_id": "hub-worker",
        "actor_kind": "agent",
        "actor_role": "implementer",
        "session_id": "session-1",
        "source": "agent_hub",
    }
    GH.contribute_context(
        graph_dir,
        type="finding",
        title="Observability state",
        content="initial",
        node_id="finding-1",
        provenance=provenance,
    )
    GH.contribute_context(
        graph_dir,
        type="finding",
        title="Observability state",
        content="updated",
        node_id="finding-1",
        provenance=provenance,
    )
    entries = _history_entries(graph_dir)
    assert [entry["action"] for entry in entries] == ["node_created", "node_updated"]
    assert all(entry["actor"]["id"] == "hub-worker" for entry in entries)


def test_link_context_preserves_originating_actor(graph_dir: Path):
    GH.contribute_context(graph_dir, type="task", title="A", node_id="a")
    GH.contribute_context(graph_dir, type="task", title="B", node_id="b")
    GH.link_context(
        graph_dir,
        "a",
        "b",
        "depends_on",
        actor={"kind": "agent", "id": "hub-linker"},
    )
    entry = _history_entries(graph_dir)[-1]
    assert entry["action"] == "relationship_created"
    assert entry["actor"]["id"] == "hub-linker"
