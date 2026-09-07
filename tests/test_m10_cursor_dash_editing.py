import json
from pathlib import Path

import pytest

from grapher.cursor_cmd import install_cursor_integration, cursor_status
from grapher.graph import add_node
from grapher.model import empty_graph
from grapher.store import init_store, load_graph, save_graph
from grapher.viz.editing import (
    EditApprovalError,
    apply_approved_status_edit,
    preview_status_edit,
)


def test_cursor_install_consumes_shared_agent_contract(tmp_path: Path):
    graph_path = tmp_path / ".grapher" / "knowledge.json"
    init_store(graph_path)
    result = install_cursor_integration(
        project_root=tmp_path,
        graph=str(graph_path),
        force=True,
        ensure_init=False,
    )
    rule = (tmp_path / ".cursor" / "rules" / "grapher.mdc").read_text()
    assert result["contract_sequence"] == ["READ", "SEARCH", "ACT", "RECORD", "VALIDATE", "PUBLISH"]
    for step in result["contract_sequence"]:
        assert f"**{step}**" in rule
    status = cursor_status(project_root=tmp_path, graph=str(graph_path))
    assert status["shared_contract"] is True
    assert status["ready"] is True


def test_dash_status_edit_requires_matching_explicit_approval(tmp_path: Path):
    graph_path = tmp_path / ".grapher" / "knowledge.json"
    init_store(graph_path)
    graph = empty_graph()
    add_node(graph, id="n", type="finding", title="State", content="known", status="current")
    save_graph(graph_path, graph)

    proposal = preview_status_edit(
        graph,
        node_id="n",
        status="historical",
        reason="The implementation has been replaced.",
    )
    assert proposal["approved"] is False
    assert load_graph(graph_path)["nodes"]["n"]["status"] == "current"

    with pytest.raises(EditApprovalError, match="approval does not match"):
        apply_approved_status_edit(
            graph_path,
            proposal,
            approval_id="wrong",
            actor_id="reviewer",
        )

    result = apply_approved_status_edit(
        graph_path,
        proposal,
        approval_id=proposal["proposal_id"],
        actor_id="reviewer",
    )
    assert result["applied"] is True
    updated = load_graph(graph_path)
    assert updated["nodes"]["n"]["status"] == "historical"
    transitions = [
        node for node in updated["nodes"].values()
        if node.get("type") == "status_transition" and (node.get("meta") or {}).get("subject_id") == "n"
    ]
    assert transitions

    history = [json.loads(line) for line in (graph_path.parent / "history.jsonl").read_text().splitlines()]
    assert history[-1]["action"] == "dashboard_status_edit_approved"
    assert history[-1]["actor"]["id"] == "reviewer"


def test_dash_edit_rejects_stale_preview(tmp_path: Path):
    graph_path = tmp_path / ".grapher" / "knowledge.json"
    init_store(graph_path)
    graph = empty_graph()
    add_node(graph, id="n", type="finding", title="State", content="known", status="current")
    save_graph(graph_path, graph)
    proposal = preview_status_edit(graph, node_id="n", status="historical", reason="Superseded state")

    changed = load_graph(graph_path)
    changed["nodes"]["n"]["status"] = "deprecated"
    save_graph(graph_path, changed)

    with pytest.raises(EditApprovalError, match="changed since preview"):
        apply_approved_status_edit(
            graph_path,
            proposal,
            approval_id=proposal["proposal_id"],
            actor_id="reviewer",
        )
