"""CASSIO curation dry-run tests (never mutates fixture)."""

from __future__ import annotations

import json
from pathlib import Path

from pathlib import Path

from grapher.cassio_curate import curate_cassio

FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _copy_fixture_to_tmp(name: str, tmp_path: Path) -> Path:
    graph_dir = tmp_path / ".grapher"
    graph_dir.mkdir(parents=True, exist_ok=True)
    dest = graph_dir / "knowledge.json"
    dest.write_text((FIXTURES / name).read_text(encoding="utf-8"), encoding="utf-8")
    return dest


def test_cassio_curate_dry_run_on_fixture(tmp_path: Path):
    graph_path = _copy_fixture_to_tmp("cassio-brain.json", tmp_path)
    report = curate_cassio(graph_path, dry_run=True)

    assert report["dry_run"] is True
    assert len(report["concepts_repaired"]) == 7
    assert len(report["checkpoints_created"]) == 6
    assert report["isolated_linked"] >= 8

    # Fixture must remain unchanged
    original = _load_fixture("cassio-brain.json")
    after = json.loads(graph_path.read_text(encoding="utf-8"))
    assert after == original


def test_cassio_curate_apply_on_copy(tmp_path: Path):
    graph_path = _copy_fixture_to_tmp("cassio-brain.json", tmp_path)
    report = curate_cassio(graph_path, dry_run=False)

    data = json.loads(graph_path.read_text(encoding="utf-8"))
    assert data["graph"]["name"] == "cassio-brain"
    assert data["graph"]["domain"] == "software"
    assert "checkpoint-current-loop-engine" in data["nodes"]
    assert report["edges_deduped"] >= 0

    fx = data["nodes"]["finding-fx-library-sample-track"]
    assert fx["status"] == "current"
    crash = data["nodes"]["finding-crash-persist-storm"]
    assert crash["status"] == "historical"
    assert crash["verification"] == "verified"

    supersedes = [
        e
        for e in data["edges"]
        if e.get("rel") == "supersedes"
        and e.get("from") == "finding-fx-library-sample-track"
        and e.get("to") == "finding-sample-edit-pages-fx"
    ]
    assert len(supersedes) == 1

    # Original semantic nodes are preserved (+ checkpoints); status curation now
    # appends immutable transition records instead of hiding those mutations.
    semantic_nodes = [
        node for node in data["nodes"].values() if node.get("type") != "status_transition"
    ]
    transitions = [
        node for node in data["nodes"].values() if node.get("type") == "status_transition"
    ]
    assert len(semantic_nodes) == 174 + 6
    assert transitions
