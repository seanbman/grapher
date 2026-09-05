from __future__ import annotations

import json
from pathlib import Path

import pytest

from grapher.graph import add_node
from grapher.store import init_store, load_graph, save_graph
from grapher.transport import graph_hash, publish_graph, shared_paths, sync_graph


def _graph_path(tmp_path: Path) -> Path:
    path = tmp_path / ".grapher" / "knowledge.json"
    init_store(path, name="transport-test")
    return path


def test_publish_writes_deterministic_shared_snapshot_and_immutable_record(tmp_path: Path):
    path = _graph_path(tmp_path)
    graph = load_graph(path)
    add_node(graph, id="component-a", type="component", title="A", content="Stable component")
    save_graph(path, graph)

    first = publish_graph(path)
    paths = shared_paths(path)
    assert first["published"] is True
    assert paths["graph"].is_file()
    assert paths["manifest"].is_file()
    assert len(list(paths["history"].glob("*.json"))) == 1

    shared = json.loads(paths["graph"].read_text(encoding="utf-8"))
    manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    assert manifest["graph_hash"] == graph_hash(shared)

    second = publish_graph(path)
    assert second["published"] is False
    assert second["reason"] == "unchanged"
    assert len(list(paths["history"].glob("*.json"))) == 1


def test_sync_refuses_to_overwrite_unpublished_local_changes(tmp_path: Path):
    path = _graph_path(tmp_path)
    graph = load_graph(path)
    add_node(graph, id="component-a", type="component", title="A")
    save_graph(path, graph)
    publish_graph(path)

    dirty = load_graph(path)
    add_node(dirty, id="component-b", type="component", title="Unpublished")
    save_graph(path, dirty)

    with pytest.raises(ValueError, match="unpublished changes"):
        sync_graph(path, rebuild_vectors=False)

    result = sync_graph(path, force=True, rebuild_vectors=False)
    assert result["synced"] is True
    assert "component-b" not in load_graph(path)["nodes"]


def test_sync_hydrates_missing_runtime_graph_and_keeps_vectors_local(tmp_path: Path):
    path = _graph_path(tmp_path)
    graph = load_graph(path)
    add_node(graph, id="component-a", type="component", title="A")
    save_graph(path, graph)
    published = publish_graph(path)

    path.unlink()
    vector_path = path.parent / "vectors.json"
    if vector_path.exists():
        vector_path.unlink()

    result = sync_graph(path, rebuild_vectors=False)
    assert result["graph_hash"] == published["graph_hash"]
    assert path.is_file()
    assert vector_path.exists() is False
    assert load_graph(path)["nodes"]["component-a"]["title"] == "A"
