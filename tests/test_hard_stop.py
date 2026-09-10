from __future__ import annotations

import copy

import pytest

from grapher import curate as C
from grapher import graph as G
from grapher.integrity import status_transition_nodes
from grapher.model import empty_graph
from grapher.store import load_graph, save_graph, save_graph_mutation
from grapher.transfer import TransferError, merge_graph


def _committed_graph():
    graph = empty_graph()
    G.add_node(
        graph,
        id="record-a",
        type="finding",
        title="Original finding",
        content="Original assertion",
        path="grapher://finding/original",
        status="current",
    )
    return graph


def _pending_ingest_graph():
    graph = empty_graph()
    G.add_node(
        graph,
        id="document-draft",
        type="document",
        title="draft.md",
        content="",
        path="docs/draft.md",
        status="unclassified",
        meta={"source": "ingest", "status": "pending"},
    )
    return graph


def test_add_is_create_only_by_id():
    graph = _committed_graph()
    with pytest.raises(G.GraphError, match="create-only"):
        G.add_node(
            graph,
            id="record-a",
            type="image",
            title="Accidental retype",
            content="bad rewrite",
        )
    assert graph["nodes"]["record-a"]["type"] == "finding"


def test_add_is_create_only_by_path():
    graph = _committed_graph()
    with pytest.raises(G.GraphError, match="does not upsert by path"):
        G.add_node(
            graph,
            type="finding",
            title="Duplicate path",
            content="new content",
            path="grapher://finding/original",
        )
    assert len(graph["nodes"]) == 1


def test_pending_ingest_draft_can_be_explicitly_enriched(tmp_path):
    path = tmp_path / "knowledge.json"
    save_graph(path, _pending_ingest_graph())
    before = load_graph(path, normalize=False)
    graph = load_graph(path)

    node = G.enrich_pending_node(
        graph,
        "document-draft",
        type="document",
        title="draft.md",
        content="Deeply understood document summary",
        path="docs/draft.md",
        tags=["document", "enriched"],
        status="current",
        verification="verified",
    )
    save_graph_mutation(path, graph, action="node_enriched", target=node["id"], before=before)

    saved = load_graph(path)
    assert saved["nodes"]["document-draft"]["content"] == "Deeply understood document summary"
    assert (saved["nodes"]["document-draft"].get("meta") or {}).get("status") != "pending"


def test_pending_ingest_draft_cannot_be_retyped():
    graph = _pending_ingest_graph()
    with pytest.raises((G.GraphError, ValueError), match="identity|type"):
        G.enrich_pending_node(
            graph,
            "document-draft",
            type="image",
            title="draft.md",
            content="wrong type",
            path="docs/draft.md",
        )
    assert graph["nodes"]["document-draft"]["type"] == "document"


def test_save_boundary_rejects_direct_committed_rewrite(tmp_path):
    path = tmp_path / "knowledge.json"
    save_graph(path, _committed_graph())
    before = load_graph(path, normalize=False)
    tampered = load_graph(path)
    tampered["nodes"]["record-a"]["type"] = "image"
    tampered["nodes"]["record-a"]["content"] = "rewritten history"

    with pytest.raises(ValueError, match="committed record.*immutable"):
        save_graph_mutation(path, tampered, action="node_updated", before=before)

    saved = load_graph(path)
    assert saved["nodes"]["record-a"]["type"] == "finding"
    assert saved["nodes"]["record-a"]["content"] == "Original assertion"


def test_save_boundary_rejects_committed_deletion_even_without_finalization(tmp_path):
    path = tmp_path / "knowledge.json"
    save_graph(path, _committed_graph())
    before = load_graph(path, normalize=False)
    graph = load_graph(path)
    del graph["nodes"]["record-a"]

    with pytest.raises(ValueError, match="cannot be removed"):
        save_graph_mutation(path, graph, action="node_removed", before=before)

    assert "record-a" in load_graph(path)["nodes"]


def test_existing_edges_cannot_be_removed_or_rewritten(tmp_path):
    path = tmp_path / "knowledge.json"
    graph = empty_graph()
    G.add_node(graph, id="a", type="finding", title="A", content="a")
    G.add_node(graph, id="b", type="finding", title="B", content="b")
    G.link(graph, from_id="a", to_id="b", rel="references", note="original relation")
    save_graph(path, graph)
    before = load_graph(path, normalize=False)
    tampered = load_graph(path)
    tampered["edges"][0]["note"] = "rewritten relation"

    with pytest.raises(ValueError, match="relations are append-only"):
        save_graph_mutation(path, tampered, action="curation_applied", before=before)

    assert load_graph(path)["edges"][0]["note"] == "original relation"


def test_status_transition_remains_supported(tmp_path):
    path = tmp_path / "knowledge.json"
    save_graph(path, _committed_graph())
    before = load_graph(path, normalize=False)
    graph = load_graph(path)
    C.set_status(graph, "record-a", "historical")
    save_graph_mutation(
        path,
        graph,
        action="status_changed",
        target="record-a",
        before=before,
        reason="A later correction superseded its use as current truth.",
        operation_id="hard-stop-status-test",
    )
    saved = load_graph(path)
    assert saved["nodes"]["record-a"]["status"] == "historical"
    assert status_transition_nodes(saved, "record-a")


def test_merge_graph_rejects_colliding_record_ids():
    local = _committed_graph()
    incoming = empty_graph()
    G.add_node(
        incoming,
        id="record-a",
        type="image",
        title="Overwrite attempt",
        content="incoming replacement",
    )
    with pytest.raises(TransferError, match="collides"):
        merge_graph(local, incoming)


def test_committed_graph_object_is_unchanged_when_add_collision_is_rejected():
    graph = _committed_graph()
    before = copy.deepcopy(graph)
    with pytest.raises(G.GraphError):
        G.add_node(graph, id="record-a", type="finding", title="Rewrite", content="rewrite")
    assert graph == before
