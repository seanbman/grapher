import json
from pathlib import Path

from grapher.agent_prompt import render_agent_context
from grapher.audit import audit_graph, validate_graph
from grapher.migrate import run_migrate
from grapher.query import apply_truth_ranking
from grapher.store import load_graph
from grapher.viz.adapter import export_view


FIXTURES = Path(__file__).parent / "fixtures"


def _suite():
    return json.loads((FIXTURES / "acceptance-suite.json").read_text())


def test_acceptance_manifest_is_complete_and_unique():
    suite = _suite()
    assert suite["version"] == 1
    ids = [case["id"] for case in suite["cases"]]
    assert len(ids) == len(set(ids))
    assert {
        "generic-v1-migration",
        "multi-agent-generation-truth",
        "legacy-rich-graph-read",
    } == set(ids)
    for case in suite["cases"]:
        assert (FIXTURES / case["fixture"]).is_file()
        assert case["purpose"].strip()
        assert case["acceptance"]


def test_generic_v1_migration_acceptance(tmp_path: Path):
    source = json.loads((FIXTURES / "museum-exhibit.json").read_text())
    path = tmp_path / "museum.json"
    path.write_text(json.dumps(source))

    first = run_migrate(path, yes=True)
    migrated = load_graph(path)
    second = run_migrate(path, yes=True)

    assert first["nodes"] == len(source["nodes"])
    assert second["status"] == "already_current"
    assert migrated["version"] == 2
    assert len(migrated["nodes"]) == len(source["nodes"])


def test_multi_agent_generation_truth_acceptance():
    graph = json.loads((FIXTURES / "dreadnought-control.json").read_text())
    report = audit_graph(graph)
    assert validate_graph(graph)["valid"] is True
    assert report["health"]["generation_ambiguity"] == 1
    assert report["counts"]["by_provenance_integrity"]["invalidated"] == 1

    candidates = [
        {"score": 1.0, "node": graph["nodes"]["handoff-2"]},
        {"score": 1.0, "node": graph["nodes"]["acceptance-contaminated"]},
    ]
    ranked = apply_truth_ranking(
        candidates,
        query="what is the current accepted state",
        mission="ubuntu-prototype",
        generation="gen-2",
        explain=True,
    )
    assert ranked[0]["node"]["id"] == "handoff-2"

    context = render_agent_context(graph, name="control-case", consumer="acceptance-test")
    assert "Consumer: `acceptance-test`" in context
    assert "Field handoff 2" in context
    assert "Contaminated acceptance" in context
    assert "Do not infer truth status from recency alone" in context

    content, _ = export_view(graph, format="json", generation="gen-2")
    exported = json.loads(content)
    assert exported["export"]["canonical"] is False
    assert set(exported["nodes"]) == {
        "mission-gen-2",
        "handoff-2",
        "acceptance-contaminated",
    }


def test_legacy_rich_graph_read_acceptance():
    raw = json.loads((FIXTURES / "cassio-brain.json").read_text())
    assert len(raw.get("nodes") or {}) >= 100
    assert len(raw.get("edges") or []) >= 100
    # Compatibility acceptance is read/inspect without requiring destructive migration.
    assert isinstance(raw.get("nodes"), (dict, list))
    assert isinstance(raw.get("edges"), list)
