"""CLI smoke tests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from grapher.graph import add_node
from grapher.store import init_store, load_graph, save_graph

FIXTURES = Path(__file__).parent / "fixtures"
GRAPH = FIXTURES / "cassio-brain.json"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, "-m", "grapher", *args]
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def _graph_path(tmp_path: Path) -> Path:
    graph_path = tmp_path / ".grapher" / "knowledge.json"
    init_store(graph_path, name="test", domain="software", profile="software")
    return graph_path


def _history_entries(graph_path: Path) -> list[dict]:
    history = graph_path.parent / "history.jsonl"
    return [json.loads(line) for line in history.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_help_exits_zero():
    r = _run("help")
    assert r.returncode == 0
    assert "grapher" in r.stdout.lower() or "usage" in r.stdout.lower()


def test_validate_fixture():
    r = _run("validate", "--graph", str(GRAPH), "--json")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["valid"] is True


def test_migrate_dry_run_schema_only():
    r = _run("migrate", "--dry-run", "--graph", str(GRAPH), "--json")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["inferred"] is False
    assert data["nodes"] == 174


def test_migrate_infer_preview():
    r = _run("migrate", "infer-preview", "--graph", str(GRAPH), "--json")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["action"] == "infer_preview"
    assert "records" in data


def test_migrate_infer_apply_requires_yes(tmp_path: Path):
    graph = tmp_path / "knowledge.json"
    graph.write_text(GRAPH.read_text(encoding="utf-8"), encoding="utf-8")
    r = _run("migrate", "infer-apply", "--graph", str(graph), "--json")
    assert r.returncode != 0
    assert "yes" in r.stderr.lower() or "yes" in r.stdout.lower()


def test_curate_cassio_dry_run():
    r = _run("curate", "cassio", "--dry-run", "--graph", str(GRAPH), "--json")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["action"] == "curate_cassio"
    assert data["dry_run"] is True


def test_link_preserves_actor(tmp_path: Path):
    graph_path = _graph_path(tmp_path)
    graph = load_graph(graph_path)
    add_node(graph, id="a", type="task", title="A")
    add_node(graph, id="b", type="task", title="B")
    save_graph(graph_path, graph)
    r = _run(
        "link",
        "a",
        "b",
        "--rel",
        "depends_on",
        "--graph",
        str(graph_path),
        "--actor",
        "linker",
        "--actor-kind",
        "agent",
        "--reason",
        "wire tasks",
    )
    assert r.returncode == 0, r.stderr
    entry = _history_entries(graph_path)[-1]
    assert entry["action"] == "relationship_created"
    assert entry["actor"]["id"] == "linker"


def test_rm_preserves_actor(tmp_path: Path):
    graph_path = _graph_path(tmp_path)
    graph = load_graph(graph_path)
    add_node(graph, id="n", type="claim", title="N")
    save_graph(graph_path, graph)
    r = _run("rm", "n", "--graph", str(graph_path), "--actor", "janitor", "--actor-kind", "agent", "--reason", "cleanup")
    assert r.returncode == 0, r.stderr
    entry = _history_entries(graph_path)[-1]
    assert entry["action"] == "node_removed"
    assert entry["actor"]["id"] == "janitor"


def test_curate_status_preserves_actor(tmp_path: Path):
    graph_path = _graph_path(tmp_path)
    graph = load_graph(graph_path)
    add_node(graph, id="n", type="claim", title="N", status="proposed")
    save_graph(graph_path, graph)
    r = _run(
        "curate",
        "status",
        "n",
        "current",
        "--graph",
        str(graph_path),
        "--actor",
        "curator",
        "--actor-kind",
        "agent",
        "--reason",
        "verified current state",
    )
    assert r.returncode == 0, r.stderr
    entry = _history_entries(graph_path)[-1]
    assert entry["action"] == "status_changed"
    assert entry["actor"]["id"] == "curator"


def test_ingest_preserves_actor(tmp_path: Path):
    graph_path = _graph_path(tmp_path)
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "note.txt").write_text("hello\n", encoding="utf-8")
    r = _run(
        "ingest",
        str(docs_dir),
        "--graph",
        str(graph_path),
        "--actor",
        "ingester",
        "--actor-kind",
        "agent",
        "--reason",
        "queue enrichment",
    )
    assert r.returncode == 0, r.stderr
    entry = _history_entries(graph_path)[-1]
    assert entry["action"] == "ingest_queued"
    assert entry["actor"]["id"] == "ingester"


def test_checkpoint_preserves_actor(tmp_path: Path):
    graph_path = _graph_path(tmp_path)
    graph = load_graph(graph_path)
    add_node(graph, id="source", type="finding", title="Source")
    save_graph(graph_path, graph)
    r = _run(
        "checkpoint",
        "create",
        "--title",
        "Snapshot",
        "--nodes",
        "source",
        "--graph",
        str(graph_path),
        "--actor",
        "checkpointer",
        "--actor-kind",
        "agent",
        "--reason",
        "capture state",
    )
    assert r.returncode == 0, r.stderr
    entry = _history_entries(graph_path)[-1]
    assert entry["action"] == "checkpoint_create"
    assert entry["actor"]["id"] == "checkpointer"


def test_infer_links_preserves_actor(tmp_path: Path):
    graph_path = _graph_path(tmp_path)
    graph = load_graph(graph_path)
    add_node(graph, id="comp-obs", type="component", title="Observability")
    add_node(
        graph,
        id="doc-1",
        type="document",
        title="observer.py",
        path="src/agent_hub/observability/observer.py",
    )
    save_graph(graph_path, graph)
    (graph_path.parent / "config.json").write_text(
        '{"component_link_rules":[{"path_prefix":"src/agent_hub/observability/","component_id":"comp-obs"}]}\n',
        encoding="utf-8",
    )
    r = _run(
        "infer-links",
        "--graph",
        str(graph_path),
        "--actor",
        "inferer",
        "--actor-kind",
        "agent",
        "--reason",
        "apply configured links",
    )
    assert r.returncode == 0, r.stderr
    entry = _history_entries(graph_path)[-1]
    assert entry["action"] == "curation_applied"
    assert entry["actor"]["id"] == "inferer"


def test_force_finalized_requires_explicit_actor_and_reason(tmp_path: Path):
    graph_path = _graph_path(tmp_path)
    graph = load_graph(graph_path)
    add_node(
        graph,
        id="a",
        type="acceptance",
        title="Accepted",
        content="decision",
        finalized_at="2026-01-01T00:00:00+00:00",
    )
    save_graph(graph_path, graph)
    r = _run(
        "add",
        "--id",
        "a",
        "--type",
        "acceptance",
        "--title",
        "Accepted",
        "--content",
        "changed",
        "--force-finalized",
        "--graph",
        str(graph_path),
    )
    assert r.returncode != 0
    assert "--force-finalized requires explicit" in (r.stderr or r.stdout)


def test_force_finalized_delete_requires_audit_and_journals_admin_removal(tmp_path: Path):
    graph_path = _graph_path(tmp_path)
    graph = load_graph(graph_path)
    add_node(
        graph,
        id="a",
        type="acceptance",
        title="Accepted",
        content="decision",
        finalized_at="2026-01-01T00:00:00+00:00",
    )
    save_graph(graph_path, graph)
    denied = _run("rm", "a", "--force-finalized", "--graph", str(graph_path))
    assert denied.returncode != 0
    assert "requires explicit" in (denied.stderr or denied.stdout)

    allowed = _run(
        "rm",
        "a",
        "--force-finalized",
        "--graph",
        str(graph_path),
        "--actor",
        "admin",
        "--actor-kind",
        "human",
        "--reason",
        "remove contaminated forensic test record",
    )
    assert allowed.returncode == 0, allowed.stderr
    assert "a" not in load_graph(graph_path)["nodes"]
    entry = _history_entries(graph_path)[-1]
    assert entry["action"] == "node_removed_administratively"
    assert entry["actor"]["id"] == "admin"
    assert entry["context"]["administrative"] is True
    assert entry["context"]["force_finalized"] is True
