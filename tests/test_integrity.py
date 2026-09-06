from __future__ import annotations

import copy
import json

import pytest

from grapher import curate as C
from grapher import graph as G
from grapher.integrity import (
    STATUS_TRANSITION_REL,
    effective_status,
    semantic_hash,
    status_transition_nodes,
    status_transition_payload,
    validate_graph_integrity,
    verify_node_integrity,
)
from grapher.model import empty_graph
from grapher.store import load_graph, save_graph, save_graph_mutation


def decision_content(decision: str = "Use immutable status transitions") -> str:
    return json.dumps(
        {
            "decision": decision,
            "rationale": "Preserve the original assertion while making later interpretation accountable.",
        }
    )


def test_semantic_hash_protects_meaning_but_survives_status_and_id_changes() -> None:
    graph = empty_graph()
    node = G.add_node(
        graph,
        id="decision-a",
        type="decision",
        title="Immutable status transitions",
        content=decision_content(),
        status="proposed",
        source_refs=["conversation:2026-09-06"],
    )
    baseline = semantic_hash(node)

    changed = copy.deepcopy(node)
    changed["status"] = "current"
    changed["updated_at"] = "2099-01-01T00:00:00+00:00"
    changed["id"] = "imported-decision-a"
    assert semantic_hash(changed) == baseline

    changed["content"] = decision_content("Rewrite status in place")
    assert semantic_hash(changed) != baseline


def test_semantic_hash_canonicalizes_structured_json_content() -> None:
    graph = empty_graph()
    node = G.add_node(
        graph,
        id="decision-json",
        type="decision",
        title="Canonical JSON",
        content=decision_content(),
    )
    reordered = copy.deepcopy(node)
    reordered["content"] = '{\n  "rationale": "Preserve the original assertion while making later interpretation accountable.",\n  "decision": "Use immutable status transitions"\n}'
    assert semantic_hash(reordered) == semantic_hash(node)


def test_status_change_creates_hashed_finalized_child_and_seals_subject(tmp_path) -> None:
    path = tmp_path / "knowledge.json"
    graph = empty_graph()
    G.add_node(
        graph,
        id="decision-a",
        type="decision",
        title="Immutable status transitions",
        content=decision_content(),
        status="proposed",
    )
    save_graph(path, graph)

    before = load_graph(path, normalize=False)
    working = load_graph(path)
    C.set_status(working, "decision-a", "current")
    entry = save_graph_mutation(
        path,
        working,
        action="status_changed",
        target="decision-a",
        before=before,
        source="test",
        actor={"kind": "human", "id": "tester"},
        reason="Architecture decision accepted after review.",
        operation_id="operation-status-1",
    )

    saved = load_graph(path)
    subject = saved["nodes"]["decision-a"]
    assert subject["status"] == "current"
    assert subject.get("finalized_at")
    assert verify_node_integrity(subject)["valid"]

    transitions = status_transition_nodes(saved, "decision-a")
    assert len(transitions) == 1
    transition = transitions[0]
    payload = status_transition_payload(transition)
    assert payload == {
        "subject_hash": subject["integrity"]["semantic_hash"],
        "from_status": "proposed",
        "to_status": "current",
        "reason": "Architecture decision accepted after review.",
        "operation_id": "operation-status-1",
    }
    assert transition.get("finalized_at")
    assert verify_node_integrity(transition)["valid"]
    assert any(
        edge.get("from") == "decision-a"
        and edge.get("to") == transition["id"]
        and edge.get("rel") == STATUS_TRANSITION_REL
        for edge in saved["edges"]
    )
    assert transition["id"] in entry["context"]["status_transition_ids"]
    assert validate_graph_integrity(saved)["valid"]


def test_successive_status_changes_preserve_assertion_hash(tmp_path) -> None:
    path = tmp_path / "knowledge.json"
    graph = empty_graph()
    G.add_node(
        graph,
        id="decision-a",
        type="decision",
        title="Immutable status transitions",
        content=decision_content(),
        status="proposed",
    )
    save_graph(path, graph)

    before = load_graph(path, normalize=False)
    working = load_graph(path)
    C.set_status(working, "decision-a", "current")
    save_graph_mutation(
        path,
        working,
        action="status_changed",
        before=before,
        reason="Accepted.",
        operation_id="operation-status-1",
        source="test",
    )
    first = load_graph(path)
    assertion_hash = first["nodes"]["decision-a"]["integrity"]["semantic_hash"]

    before = load_graph(path, normalize=False)
    working = load_graph(path)
    C.set_status(working, "decision-a", "historical")
    save_graph_mutation(
        path,
        working,
        action="status_changed",
        before=before,
        reason="A later architecture replaced this decision.",
        operation_id="operation-status-2",
        source="test",
    )
    saved = load_graph(path)

    assert saved["nodes"]["decision-a"]["integrity"]["semantic_hash"] == assertion_hash
    assert effective_status(saved, "decision-a") == "historical"
    transitions = status_transition_nodes(saved, "decision-a")
    assert [status_transition_payload(node)["to_status"] for node in transitions] == [
        "current",
        "historical",
    ]
    assert all(
        status_transition_payload(node)["subject_hash"] == assertion_hash
        for node in transitions
    )
    assert validate_graph_integrity(saved)["valid"]


def test_finalized_semantic_tampering_is_rejected_before_save(tmp_path) -> None:
    path = tmp_path / "knowledge.json"
    graph = empty_graph()
    G.add_node(
        graph,
        id="decision-a",
        type="decision",
        title="Immutable status transitions",
        content=decision_content(),
        status="proposed",
    )
    save_graph(path, graph)

    before = load_graph(path, normalize=False)
    working = load_graph(path)
    C.set_status(working, "decision-a", "current")
    save_graph_mutation(
        path,
        working,
        action="status_changed",
        before=before,
        reason="Accepted.",
        operation_id="operation-status-1",
        source="test",
    )

    before = load_graph(path, normalize=False)
    tampered = load_graph(path)
    tampered["nodes"]["decision-a"]["title"] = "Tampered decision"
    with pytest.raises(ValueError, match="semantic integrity mismatch"):
        save_graph_mutation(
            path,
            tampered,
            action="node_updated",
            before=before,
            source="test",
        )
    assert load_graph(path)["nodes"]["decision-a"]["title"] == "Immutable status transitions"


def test_superseding_finalized_record_creates_status_transition(tmp_path) -> None:
    path = tmp_path / "knowledge.json"
    graph = empty_graph()
    G.add_node(
        graph,
        id="old",
        type="decision",
        title="Old architecture",
        content=decision_content("Use mutable status fields"),
        status="current",
    )
    save_graph(path, graph)

    # Force the old assertion across the semantic boundary by changing its status once.
    before = load_graph(path, normalize=False)
    working = load_graph(path)
    C.set_status(working, "old", "proposed")
    save_graph_mutation(
        path,
        working,
        action="status_changed",
        before=before,
        reason="Reopened for architecture review.",
        operation_id="operation-reopen",
        source="test",
    )

    before = load_graph(path, normalize=False)
    working = load_graph(path)
    G.add_node(
        working,
        id="new",
        type="decision",
        title="Immutable transition architecture",
        content=decision_content(),
        status="current",
    )
    C.supersede(working, "new", "old", note="Immutable transition architecture replaced direct mutation.")
    save_graph_mutation(
        path,
        working,
        action="node_superseded",
        before=before,
        source="test",
        operation_id="operation-supersede",
    )

    saved = load_graph(path)
    assert saved["nodes"]["old"]["status"] == "superseded"
    assert any(edge.get("from") == "new" and edge.get("to") == "old" and edge.get("rel") == "supersedes" for edge in saved["edges"])
    latest = status_transition_payload(status_transition_nodes(saved, "old")[-1])
    assert latest["to_status"] == "superseded"
    assert latest["reason"].startswith("Superseded by new:")
    assert validate_graph_integrity(saved)["valid"]
