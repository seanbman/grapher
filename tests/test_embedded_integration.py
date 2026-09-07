"""Contract tests for the host-agnostic embedded Grapher API."""

import json
from pathlib import Path

from grapher.integrations import embedded as E
from grapher.store import init_store, load_graph


def test_embedded_contribution_uses_canonical_mutation_history(tmp_path: Path):
    graph_path = tmp_path / ".grapher" / "knowledge.json"
    init_store(graph_path, name="embedded-test", domain="software", profile="software")

    node = E.contribute_context(
        graph_path,
        type="finding",
        title="Embedded write",
        content="written through the supported host boundary",
        node_id="embedded-1",
        status="current",
        provenance={
            "actor_id": "host-control-plane",
            "actor_kind": "system_tool",
            "actor_role": "control-plane",
            "source": "host-application",
        },
        source="host-application",
    )

    graph = load_graph(graph_path)
    assert graph["nodes"][node["id"]]["title"] == "Embedded write"

    history_path = graph_path.parent / "history.jsonl"
    entries = [
        json.loads(line)
        for line in history_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert entries[-1]["action"] == "node_created"
    assert entries[-1]["actor"]["id"] == "host-control-plane"
    assert entries[-1]["source"] == "host-application"


def test_embedded_surface_remains_host_agnostic():
    assert "agent_hub" not in E.__doc__.lower()
    assert callable(E.query_context)
    assert callable(E.contribute_context)
    assert callable(E.link_context)
