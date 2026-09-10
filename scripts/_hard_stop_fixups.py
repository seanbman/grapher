from __future__ import annotations

from pathlib import Path
import re


def read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    Path(path).write_text(text, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    text = read(path)
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one occurrence, found {count}")
    write(path, text.replace(old, new, 1))


# Same-path records are allowed; path is no longer an implicit upsert selector.
graph = read("src/grapher/graph.py")
path_block = '''    if path:
        want = Path(path).as_posix()
        for existing in nodes.values():
            existing_path = existing.get("path")
            if existing_path and Path(existing_path).as_posix() == want:
                raise GraphError(
                    f"path {path!r} is already represented by node {existing.get('id')!r}; "
                    "grapher add does not upsert by path"
                )

'''
if path_block not in graph:
    raise SystemExit("graph.py path-collision block missing")
graph = graph.replace(path_block, "", 1)
graph = graph.replace("    from pathlib import Path\n\n    nodes = graph[\"nodes\"]", "    nodes = graph[\"nodes\"]", 1)
write("src/grapher/graph.py", graph)

hard_tests = read("tests/test_hard_stop.py")
old = '''def test_add_is_create_only_by_path():
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
'''
new = '''def test_same_path_creates_distinct_record_instead_of_upserting():
    graph = _committed_graph()
    created = G.add_node(
        graph,
        id="record-b",
        type="finding",
        title="Independent finding from same source",
        content="new content",
        path="grapher://finding/original",
    )
    assert created["id"] == "record-b"
    assert len(graph["nodes"]) == 2
    assert graph["nodes"]["record-a"]["content"] == "Original assertion"
'''
if old not in hard_tests:
    raise SystemExit("hard-stop path test target missing")
write("tests/test_hard_stop.py", hard_tests.replace(old, new, 1))

# Legacy one-shot Cassio curation is now explicitly review-only because applying it rewrites records.
cassio = read("src/grapher/cassio_curate.py")
needle = '''    if not dry_run:
        mutation_context = {"kind": "cassio_acceptance"}
'''
replacement = '''    if not dry_run:
        raise ValueError(
            "cassio curate apply is disabled by the hard-stop immutable-record policy; "
            "use the dry-run report to create new correcting records instead"
        )
        mutation_context = {"kind": "cassio_acceptance"}
'''
if needle not in cassio:
    raise SystemExit("cassio apply target missing")
write("src/grapher/cassio_curate.py", cassio.replace(needle, replacement, 1))

cassio_tests = read("tests/test_cassio_curate.py")
cassio_tests = cassio_tests.replace(
    "    report = curate_cassio(graph_path, dry_run=False)\n",
    "    import pytest\n\n    with pytest.raises(ValueError, match=\"hard-stop immutable-record policy\"):\n        curate_cassio(graph_path, dry_run=False)\n    return\n",
    1,
)
write("tests/test_cassio_curate.py", cassio_tests)

# Agent-Hub update semantics become append-only revision + supersession.
integration = read("src/grapher/integrations/agent_hub.py")
integration = integration.replace("import copy\n", "import copy\nimport uuid\n", 1)
integration = integration.replace("from grapher import graph as G\n", "from grapher import graph as G\nfrom grapher import curate as C\n", 1)
old = '''    edge_count_before = len(before.get("edges") or [])
    node = G.add_node(
        graph,
        type=type,
        title=title,
        content=content,
        id=node_id,
        path=path,
        tags=tags,
        status=status, workflow_state=workflow_state, verification=verification,
        evidence=evidence, scope=scope, provenance=provenance, finalized_at=finalized_at,
    )
    existing = before.get("nodes", {}).get(node["id"])
'''
new = '''    edge_count_before = len(before.get("edges") or [])
    original_id = node_id if node_id and node_id in (before.get("nodes") or {}) else None
    effective_id = node_id
    if original_id:
        effective_id = f"{node_id}-revision-{uuid.uuid4().hex[:8]}"
    node = G.add_node(
        graph,
        type=type,
        title=title,
        content=content,
        id=effective_id,
        path=path,
        tags=tags,
        status=status, workflow_state=workflow_state, verification=verification,
        evidence=evidence, scope=scope, provenance=provenance, finalized_at=finalized_at,
    )
    existing = before.get("nodes", {}).get(node["id"])
    if original_id:
        C.supersede(
            graph,
            node["id"],
            original_id,
            note="append-only revision created by integration contribution",
        )
'''
if old not in integration:
    raise SystemExit("agent_hub contribute target missing")
integration = integration.replace(old, new, 1)
integration = integration.replace(
    '    action = "node_created" if existing is None else "node_updated"\n',
    '    action = "node_superseded" if original_id else "node_created"\n',
    1,
)
write("src/grapher/integrations/agent_hub.py", integration)

integration_tests = read("tests/test_integrations.py")
integration_tests = integration_tests.replace(
    'def test_contribute_context_preserves_originating_actor_and_create_update_labels(graph_dir: Path):',
    'def test_contribute_context_preserves_originating_actor_and_appends_revision(graph_dir: Path):',
    1,
)
integration_tests = integration_tests.replace(
    '    assert [entry["action"] for entry in entries] == ["node_created", "node_updated"]\n    assert all(entry["actor"]["id"] == "hub-worker" for entry in entries)\n',
    '    assert [entry["action"] for entry in entries] == ["node_created", "node_superseded"]\n    assert all(entry["actor"]["id"] == "hub-worker" for entry in entries)\n    graph = load_graph(graph_dir)\n    revisions = [node for node in graph["nodes"].values() if node["id"].startswith("finding-1-revision-")]\n    assert len(revisions) == 1\n    assert graph["nodes"]["finding-1"]["content"] == "initial"\n    assert graph["nodes"]["finding-1"]["status"] == "superseded"\n    assert any(edge["from"] == revisions[0]["id"] and edge["to"] == "finding-1" and edge["rel"] == "supersedes" for edge in graph["edges"])\n',
    1,
)
write("tests/test_integrations.py", integration_tests)

# Hard-stop catches tampering earlier than the semantic seal; update the expected diagnostic.
integrity_tests = read("tests/test_integrity.py")
integrity_tests = integrity_tests.replace(
    'with pytest.raises(ValueError, match="semantic integrity mismatch"):',
    'with pytest.raises(ValueError, match="committed record.*immutable"):',
    1,
)
write("tests/test_integrity.py", integrity_tests)

# Existing finalized tests now hit the stronger create-only/committed-record boundary first.
modern = read("tests/test_modernization.py")
modern = modern.replace('with pytest.raises(GraphError, match="finalized"):', 'with pytest.raises(GraphError, match="create-only"):', 2)
# The parameterized block contributes 15 additional identical expectations.
modern = modern.replace('with pytest.raises(GraphError, match="finalized"):', 'with pytest.raises(GraphError, match="create-only"):')
# Removal now reports the broader committed-record invariant.
modern = modern.replace('with pytest.raises(GraphError, match="create-only"):\n        from grapher.graph import remove_node\n\n        remove_node(graph, "a")', 'with pytest.raises(GraphError, match="committed record"):\n        from grapher.graph import remove_node\n\n        remove_node(graph, "a")', 1)
write("tests/test_modernization.py", modern)

# Evidence is assertion-bearing. Operational state may change, but evidence must be a new record/relation.
prov = read("tests/test_provenance.py")
prov = prov.replace(
    '    graph["nodes"]["req"].update(status="current", workflow_state="completed",\n                                  verification="verified",\n                                  evidence=[{"type": "test", "ref": "pytest"}])\n',
    '    graph["nodes"]["req"].update(status="current", workflow_state="completed",\n                                  verification="verified")\n',
    1,
)
prov = prov.replace(
    '    assert {"node_status_changed", "workflow_state_changed",\n            "verification_state_changed", "evidence_attached"} <= kinds\n',
    '    assert {"node_status_changed", "workflow_state_changed",\n            "verification_state_changed"} <= kinds\n    assert "evidence_attached" not in kinds\n',
    1,
)
write("tests/test_provenance.py", prov)

# Legacy semantic records can no longer use add as an update path.
semantic_tests = read("tests/test_semantic.py")
semantic_tests = re.sub(
    r'def test_unchanged_legacy_semantic_content_can_be_operationally_updated\(\):.*?\n\ndef test_rewriting_legacy_semantic_content_requires_normalization\(\):',
'''def test_legacy_semantic_record_cannot_be_updated_through_add():
    graph = empty_graph()
    graph["nodes"]["legacy"] = {
        "id": "legacy",
        "type": "decision",
        "title": "Legacy decision",
        "content": "old free-form decision",
        "status": "unclassified",
        "workflow_state": "not_applicable",
        "verification": "unverified",
        "evidence": [],
        "source_refs": [],
        "owners": [],
        "meta": {},
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
    }
    with pytest.raises(GraphError, match="create-only"):
        add_node(
            graph,
            id="legacy",
            type="decision",
            title="Legacy decision",
            content="old free-form decision",
            workflow_state="active",
        )


def test_rewriting_legacy_semantic_content_requires_normalization():''',
    semantic_tests,
    count=1,
    flags=re.S,
)
semantic_tests = semantic_tests.replace(
    '    with pytest.raises(ValueError, match="JSON object"):\n        add_node(',
    '    with pytest.raises(GraphError, match="create-only"):\n        add_node(',
    1,
)
write("tests/test_semantic.py", semantic_tests)

# Version test follows the release version.
replace_once("tests/test_version.py", 'assert grapher.__version__ == "0.7.0b1"', 'assert grapher.__version__ == "0.7.0b2"')

# These installer tests were stale on main: installer now intentionally includes dash as well as embed.
install_tests = read("tests/test_install_script.py")
install_tests = install_tests.replace('pip install --upgrade "$SCRIPT_DIR[embed]"', 'pip install --upgrade "$SCRIPT_DIR[embed,dash]"')
install_tests = install_tests.replace('grapher[embed] @ git+https://github.com/$REPO.git@$TAG', 'grapher[embed,dash] @ git+https://github.com/$REPO.git@$TAG')
write("tests/test_install_script.py", install_tests)
