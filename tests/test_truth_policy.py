from __future__ import annotations

from pathlib import Path

import pytest

from grapher.config import default_config, save_config
from grapher.graph import add_node
from grapher.store import load_graph, save_graph, save_graph_mutation
from grapher.model import empty_graph
from grapher.truth_policy import (
    newly_unclassified_authored_node_ids,
    unclassified_authored_node_ids,
)


def _strict_graph(tmp_path: Path) -> tuple[Path, dict]:
    path = tmp_path / ".grapher" / "knowledge.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    graph = empty_graph()
    save_graph(path, graph)
    config = default_config()
    config["require_explicit_status"] = True
    save_config(path, config)
    return path, graph


def test_strict_save_rejects_new_authored_unclassified_node(tmp_path: Path):
    path, before = _strict_graph(tmp_path)
    graph = load_graph(path)
    add_node(graph, id="doc", type="document", title="Authored document", content="meaningful")

    assert newly_unclassified_authored_node_ids(before, graph) == ["doc"]
    with pytest.raises(ValueError, match="explicit truth status required"):
        save_graph_mutation(path, graph, action="node_created", target="doc", before=before)

    assert "doc" not in load_graph(path, normalize=False)["nodes"]


def test_strict_save_accepts_explicitly_classified_node(tmp_path: Path):
    path, before = _strict_graph(tmp_path)
    graph = load_graph(path)
    add_node(
        graph,
        id="doc",
        type="document",
        title="Authored document",
        content="meaningful",
        status="current",
    )

    save_graph_mutation(path, graph, action="node_created", target="doc", before=before)
    assert load_graph(path)["nodes"]["doc"]["status"] == "current"


def test_strict_save_allows_pending_ingest_review_stub(tmp_path: Path):
    path, before = _strict_graph(tmp_path)
    graph = load_graph(path)
    add_node(
        graph,
        id="stub",
        type="document",
        title="Pending source",
        meta={"source": "ingest", "status": "pending"},
    )

    save_graph_mutation(path, graph, action="node_created", target="stub", before=before)
    saved = load_graph(path)
    assert saved["nodes"]["stub"]["status"] == "unclassified"
    assert saved["nodes"]["stub"]["meta"]["status"] == "pending"


def test_truth_review_marker_and_legacy_allowlist_are_explicit_exceptions():
    graph = empty_graph()
    add_node(
        graph,
        id="review",
        type="document",
        title="Needs review",
        meta={"truth_review": True},
    )
    add_node(graph, id="legacy", type="document", title="Legacy")
    add_node(graph, id="bad", type="document", title="Bad")

    assert unclassified_authored_node_ids(
        graph,
        legacy_allowlist={"legacy"},
    ) == ["bad"]
