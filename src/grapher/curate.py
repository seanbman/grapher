"""Curate graph truth: status, relations, supersession, merge, compact."""

from __future__ import annotations

from typing import Any

from grapher.graph import (
    GraphError,
    add_node,
    assert_not_finalized,
    get_node,
    is_finalized,
    link,
    remove_node,
)
from grapher.model import make_edge, now_iso
from grapher.registry import TRUTH_STATUSES


def set_status(
    graph: dict[str, Any],
    node_id: str,
    status: str,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Update the materialized status cache through the curation boundary.

    save_graph_mutation materializes the authoritative immutable status_transition
    child. This direct cache update is therefore intentionally permitted even for
    finalized nodes; semantic fields remain immutable.
    """
    if status not in TRUTH_STATUSES:
        raise ValueError(f"unknown status {status!r}")
    node = get_node(graph, node_id)
    before = node.get("status")
    preview = {
        "action": "status",
        "node_id": node_id,
        "before": before,
        "after": status,
        "dry_run": dry_run,
    }
    if dry_run:
        return preview
    node["status"] = status
    node["updated_at"] = now_iso()
    preview["applied"] = True
    return preview


def relate(
    graph: dict[str, Any],
    from_id: str,
    to_id: str,
    rel: str,
    *,
    note: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    preview = {
        "action": "relate",
        "from": from_id,
        "to": to_id,
        "rel": rel,
        "note": note,
        "dry_run": dry_run,
    }
    if dry_run:
        get_node(graph, from_id)
        get_node(graph, to_id)
        return preview
    edge = link(graph, from_id=from_id, to_id=to_id, rel=rel, note=note)
    preview["edge"] = edge
    return preview


def supersede(
    graph: dict[str, Any],
    new_id: str,
    old_id: str,
    *,
    note: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    get_node(graph, new_id)
    get_node(graph, old_id)
    preview = {
        "action": "supersede",
        "new_id": new_id,
        "old_id": old_id,
        "dry_run": dry_run,
        "changes": [
            {"node": old_id, "status": "superseded"},
            {"edge": f"{new_id} -supersedes-> {old_id}"},
        ],
    }
    if dry_run:
        return preview
    old = get_node(graph, old_id)
    # Status is a derived compatibility cache. The authoritative change is the
    # immutable status_transition child materialized when this mutation is saved.
    old["status"] = "superseded"
    old["updated_at"] = now_iso()
    edge = link(
        graph,
        from_id=new_id,
        to_id=old_id,
        rel="supersedes",
        note=note or "superseded via curate",
    )
    preview["edge"] = edge
    return preview


def merge_nodes(
    graph: dict[str, Any],
    keep_id: str,
    drop_id: str,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    keep = get_node(graph, keep_id)
    drop = get_node(graph, drop_id)
    if keep.get("finalized_at") or drop.get("finalized_at"):
        raise GraphError("finalized records cannot be merged; supersede with a correcting node")
    preview = {
        "action": "merge",
        "keep_id": keep_id,
        "drop_id": drop_id,
        "dry_run": dry_run,
        "rewire_edges": 0,
    }
    edges = graph.get("edges") or []
    rewire = []
    for e in edges:
        if e.get("from") == drop_id or e.get("to") == drop_id:
            rewire.append(dict(e))
    preview["rewire_edges"] = len(rewire)
    if dry_run:
        return preview

    # Merge content/tags
    if drop.get("content") and drop["content"] not in (keep.get("content") or ""):
        keep["content"] = (
            (keep.get("content") or "")
            + ("\n\n--- merged from " + drop_id + " ---\n\n")
            + drop["content"]
        ).strip()
    keep_tags = set(keep.get("tags") or [])
    keep_tags.update(drop.get("tags") or [])
    keep["tags"] = sorted(keep_tags)
    keep["updated_at"] = now_iso()

    new_edges: list[dict[str, Any]] = []
    for e in edges:
        frm, to = e.get("from"), e.get("to")
        if frm == drop_id:
            frm = keep_id
        if to == drop_id:
            to = keep_id
        if frm == to:
            continue
        ne = dict(e)
        ne["from"] = frm
        ne["to"] = to
        new_edges.append(ne)
    graph["edges"] = new_edges
    remove_node(graph, drop_id)
    preview["applied"] = True
    return preview


def compact_related(
    graph: dict[str, Any], *, topic: str | None = None,
    dry_run: bool = False, limit: int = 50,
) -> dict[str, Any]:
    """Build a non-destructive, review-first compaction proposal."""
    nodes = graph.get("nodes") or {}
    edges = graph.get("edges") or []
    terms = [term for term in (topic or "").lower().split() if term]
    candidates = []
    excluded = []
    for nid, node in nodes.items():
        hay = " ".join([str(node.get("title") or ""), str(node.get("content") or ""),
                         " ".join(node.get("tags") or [])]).lower()
        if terms and not all(term in hay for term in terms):
            excluded.append({"id": nid, "reason": "topic_mismatch"})
            continue
        candidates.append(node)
    candidates = candidates[:limit]
    ids = {node["id"] for node in candidates}
    contradictions = [edge for edge in edges if edge.get("rel") == "contradicts"
                      and (edge.get("from") in ids or edge.get("to") in ids)]
    provenance_concerns = [node["id"] for node in candidates
                           if (node.get("provenance") or {}).get("integrity") in ("contested", "invalidated")]
    generations = sorted({(node.get("scope") or {}).get("generation_id") for node in candidates
                          if (node.get("scope") or {}).get("generation_id")})
    winners = [node for node in candidates if node.get("status") in ("current", "canonical_spec", "proposed")
               and node.get("status") not in ("superseded", "rejected", "deprecated")]
    content = "\n".join(f"- {node.get('title') or node['id']}: {(node.get('content') or '').strip()[:240]}"
                        for node in winners)
    relationship_suggestions = []
    for edge in edges:
        if edge.get("rel") == "related" and edge.get("from") in ids and edge.get("to") in ids:
            relationship_suggestions.append({"from": edge.get("from"), "to": edge.get("to"),
                                             "reason": "replace low-information related edge after review"})
    return {
        "action": "compact", "dry_run": dry_run, "review_only": True, "topic": topic,
        "included": [{"id": node["id"], "status": node.get("status"),
                      "generation": (node.get("scope") or {}).get("generation_id")} for node in candidates],
        "excluded": excluded[:limit], "proposed_content": content,
        "proposed_status": "current", "proposed_relationships": relationship_suggestions[:limit],
        "contradictions": contradictions, "generation_boundaries": generations,
        "provenance_concerns": provenance_concerns, "count": len(candidates),
    }


def finalize_node(graph: dict[str, Any], node_id: str, *, dry_run: bool = False) -> dict[str, Any]:
    from grapher.integrity import seal_node

    node = get_node(graph, node_id)
    preview = {"action": "finalize", "node_id": node_id, "before": node.get("finalized_at"), "dry_run": dry_run}
    if dry_run:
        return preview
    if not node.get("finalized_at"):
        seal_node(node)
        node["finalized_at"] = now_iso()
        node["updated_at"] = node["finalized_at"]
    preview["after"] = node["finalized_at"]
    preview["semantic_hash"] = (node.get("integrity") or {}).get("semantic_hash")
    return preview


def set_provenance_integrity(
    graph: dict[str, Any], node_id: str, integrity: str, *,
    reason: str | None = None, attestation_ref: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    from grapher.registry import PROVENANCE_INTEGRITIES

    if integrity not in PROVENANCE_INTEGRITIES:
        raise ValueError(f"unknown provenance integrity {integrity!r}")
    if integrity == "verified" and not attestation_ref:
        raise ValueError("verified provenance requires an external attestation reference")
    node = get_node(graph, node_id)
    assert_not_finalized(node, node_id=node_id, operation="change provenance integrity")
    old = dict(node.get("provenance") or {})
    preview = {"action": "provenance", "node_id": node_id, "before": old.get("integrity", "unknown"),
               "after": integrity, "reason": reason, "dry_run": dry_run}
    if dry_run:
        return preview
    provenance = dict(old)
    provenance["integrity"] = integrity
    provenance["recorded_at"] = now_iso()
    if reason:
        provenance["integrity_reason"] = reason
    if attestation_ref:
        provenance["attestation_ref"] = attestation_ref
    node["provenance"] = provenance
    node["updated_at"] = now_iso()
    return preview
