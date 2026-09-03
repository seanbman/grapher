from __future__ import annotations

import json
from pathlib import Path

import pytest

from grapher.audit import audit_graph, validate_graph
from grapher.checkpoint import create_checkpoint, refresh_checkpoint
from grapher.graph import GraphError, add_node
from grapher.curate import set_provenance_integrity, supersede
from grapher.migrate import run_migrate
from grapher.model import embed_text, empty_graph
from grapher.query import apply_truth_ranking, matches_filters
from grapher.registry import BUILTIN_NODE_TYPES, BUILTIN_RELS
from grapher.store import init_store, load_graph, save_graph, save_graph_mutation
from grapher.viz.adapter import filter_nodes

FIXTURES = Path(__file__).parent / "fixtures"


def test_required_multi_agent_registry_is_complete():
    assert {"mission", "session", "handoff", "acceptance", "audit_record", "event", "claim"} <= BUILTIN_NODE_TYPES
    assert {"authored_by", "performed_by", "observed_by", "hands_off", "accepts", "audits", "contradicts"} <= BUILTIN_RELS


def test_vector_identity_excludes_operational_metadata():
    node = {"title": "State", "content": "same semantics", "tags": ["x"]}
    original = embed_text(node)
    node.update(status="superseded", verification="failed", scope={"generation_id": "g2"}, provenance={"integrity": "invalidated"})
    assert embed_text(node) == original


def test_finalized_record_rejects_semantic_rewrite():
    graph = empty_graph()
    add_node(graph, id="a", type="acceptance", title="Accepted", content="decision", finalized_at="2026-01-01T00:00:00+00:00")
    with pytest.raises(GraphError, match="finalized"):
        add_node(graph, id="a", type="acceptance", title="Accepted", content="changed")
    corrected = add_node(graph, id="b", type="acceptance", title="Correction", content="correct state")
    assert corrected["id"] == "b" and graph["nodes"]["a"]["content"] == "decision"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("type", "handoff"),
        ("title", "Accepted later"),
        ("content", "changed"),
        ("path", "docs/rewritten.md"),
        ("tags", ["forensic", "rewritten"]),
        ("meta", {"channel": "rewritten"}),
        ("stage", "maintaining"),
        ("status", "historical"),
        ("workflow_state", "completed"),
        ("verification", "failed"),
        ("evidence", [{"type": "test", "ref": "recheck"}]),
        ("source_refs", ["source-2"]),
        ("owners", ["security"]),
        ("scope", {"mission_id": "m-2"}),
        ("provenance", {"actor_id": "auditor", "actor_kind": "human", "integrity": "invalidated"}),
        ("finalized_at", "2026-01-02T00:00:00+00:00"),
    ],
)
def test_finalized_record_rejects_major_semantic_field_rewrites(field: str, value):
    graph = empty_graph()
    add_node(
        graph,
        id="a",
        type="acceptance",
        title="Accepted",
        content="decision",
        path="docs/original.md",
        tags=["forensic"],
        meta={"channel": "audit"},
        stage="developing",
        status="current",
        workflow_state="active",
        verification="verified",
        evidence=[{"type": "test", "ref": "proof"}],
        source_refs=["source-1"],
        owners=["ops"],
        scope={"mission_id": "m-1"},
        provenance={"actor_id": "arbiter", "actor_kind": "human", "integrity": "declared"},
        finalized_at="2026-01-01T00:00:00+00:00",
    )
    payload = {
        "id": "a",
        "type": "acceptance",
        "title": "Accepted",
        "content": "decision",
    }
    payload[field] = value
    with pytest.raises(GraphError, match="finalized"):
        add_node(graph, **payload)


def test_finalized_record_cannot_be_removed_or_have_provenance_rewritten():
    graph = empty_graph()
    add_node(
        graph,
        id="a",
        type="acceptance",
        title="Accepted",
        content="decision",
        provenance={"actor_id": "arbiter", "actor_kind": "human", "integrity": "declared"},
        finalized_at="2026-01-01T00:00:00+00:00",
    )
    with pytest.raises(GraphError, match="finalized"):
        from grapher.graph import remove_node

        remove_node(graph, "a")
    with pytest.raises(GraphError, match="finalized"):
        set_provenance_integrity(graph, "a", "invalidated", reason="later dispute")


def test_supersede_preserves_finalized_record_and_adds_correction_edge():
    graph = empty_graph()
    add_node(
        graph,
        id="old",
        type="acceptance",
        title="Accepted",
        content="original state",
        status="current",
        finalized_at="2026-01-01T00:00:00+00:00",
    )
    add_node(graph, id="new", type="acceptance", title="Correction", content="corrected state", status="current")
    result = supersede(graph, "new", "old")
    assert result["edge"]["rel"] == "supersedes"
    assert graph["nodes"]["old"]["status"] == "current"
    assert graph["nodes"]["old"]["content"] == "original state"
    assert graph["nodes"]["old"]["finalized_at"] == "2026-01-01T00:00:00+00:00"


def test_mutation_journal_hashes_and_reads_do_not_append(tmp_path: Path):
    path = tmp_path / ".grapher" / "knowledge.json"
    init_store(path)
    before = load_graph(path, normalize=False)
    graph = load_graph(path)
    add_node(graph, id="n", type="claim", title="Claim", content="fact")
    entry = save_graph_mutation(path, graph, action="node_created", target="n", before=before)
    history = path.parent / "history.jsonl"
    lines = history.read_text().splitlines()
    assert len(lines) == 1
    assert entry["before_hash"] and entry["after_hash"] and entry["before_hash"] != entry["after_hash"]
    load_graph(path)
    assert len(history.read_text().splitlines()) == 1


def test_journal_failure_rolls_back_graph(tmp_path: Path, monkeypatch):
    path = tmp_path / ".grapher" / "knowledge.json"
    init_store(path)
    before = load_graph(path, normalize=False)
    graph = load_graph(path)
    add_node(graph, id="n", type="claim", title="Claim")
    monkeypatch.setattr("grapher.store.append_history", lambda *_: (_ for _ in ()).throw(OSError("disk full")))
    with pytest.raises(OSError, match="disk full"):
        save_graph_mutation(path, graph, action="node_created", before=before)
    assert load_graph(path, normalize=False) == before


def test_scope_filter_and_authoritative_provenance_ranking():
    good = {"id": "handoff", "title": "Ready", "status": "current", "verification": "verified",
            "scope": {"mission_id": "m", "generation_id": "g2"},
            "provenance": {"integrity": "declared"}}
    bad = {"id": "acceptance", "title": "Accepted", "status": "current", "verification": "verified",
           "scope": {"mission_id": "m", "generation_id": "g2"},
           "provenance": {"integrity": "invalidated"}}
    assert matches_filters(good, mission="m", generation="g2")
    assert not matches_filters(good, generation="g1")
    ranked = apply_truth_ranking([{"score": 1.0, "node": bad}, {"score": 1.0, "node": good}],
                                 query="what is the current accepted state", mission="m", generation="g2",
                                 explain=True)
    assert ranked[0]["node"]["id"] == "handoff"
    assert ranked[1]["ranking"]["provenance_adjustment"] < 0


def test_control_case_audit_preserves_contaminated_acceptance():
    graph = json.loads((FIXTURES / "dreadnought-control.json").read_text())
    report = audit_graph(graph)
    assert report["health"]["generation_ambiguity"] == 1
    assert report["counts"]["by_provenance_integrity"]["invalidated"] == 1
    assert "acceptance-contaminated" in graph["nodes"]
    assert validate_graph(graph)["valid"] is True


def test_checkpoint_refresh_requires_review_and_reports_diff(tmp_path: Path):
    path = tmp_path / ".grapher" / "knowledge.json"
    graph = empty_graph()
    add_node(graph, id="source", type="finding", title="State", status="current")
    result = create_checkpoint(graph, path, title="Current", node_ids=["source"])
    checkpoint = result["id"]
    graph["nodes"]["source"]["updated_at"] = "9999-01-01T00:00:00+00:00"
    preview = refresh_checkpoint(graph, path, checkpoint, dry_run=True)
    assert preview["diff"]["changed_sources"] == ["source"]
    with pytest.raises(ValueError, match="--yes"):
        refresh_checkpoint(graph, path, checkpoint)


def test_v1_dashboard_adapter_filters_normalized_generation_fixture():
    graph = json.loads((FIXTURES / "dreadnought-control.json").read_text())
    assert filter_nodes(graph, generation="gen-2") == {"mission-gen-2", "handoff-2", "acceptance-contaminated"}


def test_migration_is_idempotent_and_journaled(tmp_path: Path):
    source = json.loads((FIXTURES / "museum-exhibit.json").read_text())
    path = tmp_path / "knowledge.json"
    path.write_text(json.dumps(source))
    result = run_migrate(path, yes=True)
    assert result["nodes"] == len(source["nodes"])
    assert (tmp_path / "history.jsonl").is_file()
    current = path.read_text()
    second = run_migrate(path, yes=True)
    assert second["status"] == "already_current"
    assert path.read_text() == current


def test_query_intent_ranking_cases():
    nodes = [
        {"id": "spec", "type": "requirement", "title": "Original requirement", "status": "canonical_spec", "verification": "verified"},
        {"id": "impl", "type": "finding", "title": "Current implementation", "status": "current", "verification": "verified"},
        {"id": "incident", "type": "incident", "title": "Historical failure", "status": "historical", "verification": "verified"},
        {"id": "roadmap", "type": "milestone", "title": "Next plan", "status": "proposed", "workflow_state": "active", "verification": "unverified"},
    ]
    hits = [{"score": 1.0, "node": node} for node in nodes]
    assert apply_truth_ranking(hits, query="original requirement")[0]["node"]["id"] == "spec"
    assert apply_truth_ranking(hits, query="why did the failure happen")[0]["node"]["id"] == "incident"
    assert apply_truth_ranking(hits, query="what is planned next")[0]["node"]["id"] == "roadmap"


def test_generation_two_active_prevents_generation_one_completion(tmp_path: Path):
    from grapher.search import search

    graph = json.loads((FIXTURES / "dreadnought-control.json").read_text())
    hits = search(graph, tmp_path / "graph.json", "mission state complete", mode="lexical",
                  mission="ubuntu-prototype", truth_rank=True, limit=10)
    assert hits
    assert all((hit["node"].get("scope") or {}).get("generation_id") == "gen-2" for hit in hits)


def test_dashboard_export_has_metadata_and_does_not_mutate():
    import copy
    from grapher.viz.adapter import export_view

    graph = json.loads((FIXTURES / "dreadnought-control.json").read_text())
    before = copy.deepcopy(graph)
    content, filename = export_view(graph, format="json", view_mode="provenance", generation="gen-2")
    exported = json.loads(content)
    assert filename == "grapher-view.json"
    assert exported["export"]["canonical"] is False
    assert exported["export"]["view"] == "provenance"
    assert set(exported["nodes"]) == {"mission-gen-2", "handoff-2", "acceptance-contaminated"}
    assert graph == before
    node_csv, _ = export_view(graph, format="nodes-csv", generation="gen-2")
    edge_csv, _ = export_view(graph, format="edges-csv", generation="gen-2")
    assert "scope,provenance" in node_csv
    assert "from,to,rel" in edge_csv
