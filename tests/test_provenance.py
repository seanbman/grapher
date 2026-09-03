from __future__ import annotations

import json
from pathlib import Path

from grapher.graph import add_node, link
from grapher.model import empty_graph
from grapher.provenance import load_history, validate_history
from grapher.store import init_store, load_graph, save_graph_mutation


def _path(tmp_path: Path) -> Path:
    path = tmp_path / ".grapher" / "knowledge.json"
    init_store(path)
    return path


def test_meaningful_node_changes_are_independent_transitions(tmp_path: Path):
    path = _path(tmp_path)
    before = load_graph(path, normalize=False)
    graph = load_graph(path)
    add_node(graph, id="req", type="requirement", title="Ship", status="proposed",
             workflow_state="not_started", verification="unverified")
    created = save_graph_mutation(path, graph, action="node_created", target="req", before=before,
                                  actor={"kind": "human", "id": "owner"}, phase="proposed",
                                  reason="initial proposal", operation_id="op-1")
    assert created["operation_id"] == "op-1"
    assert created["transitions"][0]["phase"] == "proposed"
    assert created["transitions"][0]["actor"]["kind"] == "human"

    before = load_graph(path, normalize=False)
    graph = load_graph(path)
    graph["nodes"]["req"].update(status="current", workflow_state="completed",
                                  verification="verified",
                                  evidence=[{"type": "test", "ref": "pytest"}])
    saved = save_graph_mutation(path, graph, action="node_updated", target="req", before=before,
                                actor={"kind": "agent", "id": "worker"}, phase="verified",
                                decision_ids=["decision-request-verification"],
                                evidence_refs=["pytest"], operation_id="op-2")
    kinds = {item["event_type"] for item in saved["transitions"]}
    assert {"node_status_changed", "workflow_state_changed",
            "verification_state_changed", "evidence_attached"} <= kinds
    assert all(item["related_decision_ids"] == ["decision-request-verification"]
               for item in saved["transitions"])
    assert load_graph(path)["nodes"]["req"]["verification"] == "verified"


def test_override_and_outcome_metadata_remain_distinct(tmp_path: Path):
    path = _path(tmp_path)
    before = load_graph(path, normalize=False)
    graph = load_graph(path)
    add_node(graph, id="outcome", type="event", title="Verification failed",
             content="Observed test result", verification="failed")
    entry = save_graph_mutation(path, graph, action="outcome_observed", target="outcome",
                                before=before, phase="observed",
                                actor={"kind": "system_tool", "id": "pytest"},
                                decision_ids=["decision-request-verification"],
                                overrides=["transition-original"], reason="test failed")
    transition = entry["transitions"][0]
    assert transition["event_type"] == "node_created"
    assert transition["phase"] == "observed"
    assert transition["related_decision_ids"] == ["decision-request-verification"]
    assert transition["overrides_transition_ids"] == ["transition-original"]
    assert transition["resulting_value"]["verification"] == "failed"


def test_dependency_and_blocker_edges_have_typed_history(tmp_path: Path):
    path = _path(tmp_path)
    graph = load_graph(path)
    add_node(graph, id="a", type="task", title="A")
    add_node(graph, id="b", type="task", title="B")
    before = load_graph(path, normalize=False)
    link(graph, from_id="a", to_id="b", rel="depends_on")
    link(graph, from_id="b", to_id="a", rel="blocks")
    entry = save_graph_mutation(path, graph, action="relations_added", before=before)
    assert {t["event_type"] for t in entry["transitions"]} == {"dependency_added", "blocker_appeared", "node_created"}


def test_history_queries_and_validation_accept_legacy_entries(tmp_path: Path):
    path = _path(tmp_path)
    history = path.parent / "history.jsonl"
    history.write_text(json.dumps({"action": "legacy", "before_hash": "a", "after_hash": "b"}) + "\n")
    before = load_graph(path, normalize=False)
    graph = load_graph(path)
    add_node(graph, id="n", type="claim", title="N")
    save_graph_mutation(path, graph, action="node_created", target="n", before=before,
                        operation_id="correlated")
    assert len(load_history(path, entity_id="n")) == 1
    assert len(load_history(path, operation_id="correlated")) == 1
    report = validate_history(path)
    assert report["valid"] is True
    assert report["legacy_entries"] == 1
    assert report["transitions"] == 1


def test_history_actor_can_be_derived_from_context_provenance(tmp_path: Path):
    path = _path(tmp_path)
    before = load_graph(path, normalize=False)
    graph = load_graph(path)
    add_node(graph, id="n", type="claim", title="N")
    entry = save_graph_mutation(
        path,
        graph,
        action="node_created",
        target="n",
        before=before,
        source="agent_hub",
        context={
            "provenance": {
                "actor_id": "hub-worker",
                "actor_kind": "agent",
                "actor_role": "implementer",
                "session_id": "session-7",
                "source": "agent_hub",
            }
        },
    )
    assert entry["actor"]["id"] == "hub-worker"
    assert entry["transitions"][0]["actor"]["id"] == "hub-worker"
