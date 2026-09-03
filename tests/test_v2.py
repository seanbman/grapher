"""Tests for grapher v2 lifecycle work graph."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from grapher.audit import audit_graph, validate_graph
from grapher.infer import infer_node, preview_inference
from grapher.migrate import migrate_v1_to_v2, run_migrate
from grapher.model import normalize_graph
from grapher.query import infer_status_from_content
from grapher.search import lexical_search

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    with (FIXTURES / name).open(encoding="utf-8") as f:
        return json.load(f)


def test_cassio_fixture_shape():
    data = _load("cassio-brain.json")
    assert data["version"] == 1
    assert len(data["nodes"]) == 174
    assert len(data["edges"]) == 322


def test_migrate_lossless_preserves_ids():
    v1 = _load("cassio-brain.json")
    v2 = migrate_v1_to_v2(v1, name="cassio-brain", domain="software")
    assert v2["version"] == 2
    assert set(v2["nodes"].keys()) == set(v1["nodes"].keys())
    assert len(v2["edges"]) == len(v1["edges"])
    for nid, node in v1["nodes"].items():
        assert v2["nodes"][nid]["id"] == node["id"]
        assert v2["nodes"][nid]["title"] == node["title"]
        assert v2["nodes"][nid]["content"] == node["content"]


def test_migrate_schema_only_leaves_unclassified():
    v1 = _load("cassio-brain.json")
    v2 = migrate_v1_to_v2(v1)
    norm = normalize_graph(v2)
    unclassified = sum(
        1 for n in norm["nodes"].values() if n.get("status") == "unclassified"
    )
    assert unclassified == 174


def test_migrate_canonical_stage_order():
    v1 = _load("cassio-brain.json")
    v2 = migrate_v1_to_v2(v1, stages=["maintaining", "ideation", "developing"])
    assert v2["graph"]["stages"] == ["ideation", "developing", "maintaining"]


def test_infer_superseded_from_content():
    v1 = _load("cassio-brain.json")
    node = v1["nodes"]["finding-sample-edit-pages-fx"]
    rec = infer_node("finding-sample-edit-pages-fx", node, all_nodes=v1["nodes"])
    assert rec.status == "superseded"
    assert any("SUPERSEDED" in e for e in rec.explanations)


def test_infer_fx_library_current_not_historical():
    v1 = _load("cassio-brain.json")
    rec = infer_node(
        "finding-fx-library-sample-track",
        v1["nodes"]["finding-fx-library-sample-track"],
        all_nodes=v1["nodes"],
    )
    assert rec.status == "current"
    assert rec.status != "historical"
    assert any(e["rel"] == "supersedes" for e in rec.new_edges)


def test_infer_crash_confirmed_not_rejected():
    v1 = _load("cassio-brain.json")
    rec = infer_node(
        "finding-crash-persist-storm",
        v1["nodes"]["finding-crash-persist-storm"],
        all_nodes=v1["nodes"],
    )
    assert rec.status == "historical"
    assert rec.status != "rejected"
    assert rec.verification == "verified"


def test_infer_crop_saveas_current_not_proposed():
    v1 = _load("cassio-brain.json")
    rec = infer_node(
        "finding-sample-full-length-crop-saveas",
        v1["nodes"]["finding-sample-full-length-crop-saveas"],
        all_nodes=v1["nodes"],
    )
    assert rec.status == "current"
    assert rec.status != "proposed"


def test_infer_d2_sequencer_verified():
    v1 = _load("cassio-brain.json")
    rec = infer_node(
        "finding-loop-d2-step-sequencer",
        v1["nodes"]["finding-loop-d2-step-sequencer"],
        all_nodes=v1["nodes"],
    )
    assert rec.status == "current"


def test_infer_screen10_image_not_current():
    v1 = _load("cassio-brain.json")
    rec = infer_node(
        "image-p15-screen-10-save-sound-a9e6553ed8",
        v1["nodes"]["image-p15-screen-10-save-sound-a9e6553ed8"],
        all_nodes=v1["nodes"],
    )
    assert rec.status is None


def test_infer_preview_proposes_supersedes_edge():
    v1 = _load("cassio-brain.json")
    v2 = migrate_v1_to_v2(v1)
    preview = preview_inference(v2)
    edges = preview["edges"]
    assert any(
        e["from"] == "finding-fx-library-sample-track"
        and e["to"] == "finding-sample-edit-pages-fx"
        and e["rel"] == "supersedes"
        for e in edges
    )


def test_migrate_infer_requires_approve():
    import tempfile

    v1 = _load("cassio-brain.json")
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "knowledge.json"
        path.write_text(json.dumps(v1))
        with pytest.raises(ValueError, match="approve-infer"):
            run_migrate(path, infer=True, yes=True)


def test_normalize_adds_defaults():
    v1 = _load("museum-exhibit.json")
    norm = normalize_graph(v1)
    node = norm["nodes"]["idea-exhibit-theme"]
    assert node["status"] == "unclassified"


def test_validate_cassio_no_errors():
    data = normalize_graph(_load("cassio-brain.json"))
    result = validate_graph(data)
    assert result["valid"] is True
    assert result["error_count"] == 0


def test_audit_cassio_related_heavy():
    data = normalize_graph(_load("cassio-brain.json"))
    report = audit_graph(data)
    assert report["health"]["related_heavy"] is True
    assert report["counts"]["nodes"] == 174


def test_search_exclude_superseded():
    v1 = _load("cassio-brain.json")
    v2 = migrate_v1_to_v2(v1)
    v2["nodes"]["finding-sample-edit-pages-fx"]["status"] = "superseded"
    norm = normalize_graph(v2)
    hits = lexical_search(
        norm,
        "sample edit pages fx",
        exclude_superseded=True,
        limit=20,
        truth_rank=False,
    )
    ids = {h["node"]["id"] for h in hits}
    assert "finding-sample-edit-pages-fx" not in ids


def test_search_semantic_no_duplicate_graph_path(monkeypatch):
    """Regression: graph_path must not be passed twice to semantic_search."""
    from unittest.mock import MagicMock

    v1 = _load("cassio-brain.json")
    norm = normalize_graph(v1)
    path = FIXTURES / "cassio-brain.json"

    def fake_semantic(graph, graph_path, query, **kwargs):
        assert graph_path == path
        node = next(iter(graph["nodes"].values()))
        return [{"score": 0.9, "mode": "semantic", "node": node}]

    monkeypatch.setattr("grapher.search.semantic_search", fake_semantic)

    from grapher.search import search

    results = search(
        norm,
        path,
        "D2 sequencer",
        mode="semantic",
        limit=3,
        truth_rank=False,
    )
    assert isinstance(results, list)
    assert results


def test_search_truth_ranking_prefers_current():
    v1 = _load("museum-exhibit.json")
    v2 = migrate_v1_to_v2(v1)
    v2["nodes"]["idea-exhibit-theme"]["status"] = "proposed"
    v2["nodes"]["finding-tank-leak"]["status"] = "current"
    norm = normalize_graph(v2)
    hits = lexical_search(norm, "tank", limit=5, truth_rank=True)
    assert hits
    assert hits[0]["node"]["id"] == "finding-tank-leak"
