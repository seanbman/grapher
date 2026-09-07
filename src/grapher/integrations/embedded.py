"""Stable host-application API for embedding Grapher.

This module is intentionally host-agnostic. External systems may use it as the
supported application boundary instead of writing Grapher state files directly.
All mutations continue through Grapher's canonical mutation machinery.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from grapher import graph as G
from grapher.integrations.agent_hub import (
    IntegrationError,
    _history_kwargs,
    apply_delta,
    export_delta,
    get_context,
    infer_links_context,
    ingest_context,
    init_context,
    link_context,
    list_feedback,
    neighbors_context,
    query_context,
    reindex_context,
)
from grapher.store import load_graph, save_graph_mutation


def contribute_context(
    graph_path: Path,
    *,
    type: str,
    title: str,
    content: str = "",
    node_id: str | None = None,
    path: str | None = None,
    tags: list[str] | None = None,
    meta: dict[str, Any] | None = None,
    stage: str | list[str] | None = None,
    status: str | None = None,
    workflow_state: str | None = None,
    verification: str | None = None,
    evidence: list[dict[str, Any]] | None = None,
    source_refs: list[str] | None = None,
    owners: list[str] | None = None,
    scope: dict[str, Any] | None = None,
    provenance: dict[str, Any] | None = None,
    finalized_at: str | None = None,
    actor: dict[str, Any] | None = None,
    reason: str | None = None,
    evidence_refs: list[str] | None = None,
    decision_ids: list[str] | None = None,
    requirement_ids: list[str] | None = None,
    supersedes: list[str] | None = None,
    overrides: list[str] | None = None,
    operation_id: str | None = None,
    phase: str = "executed",
    source: str = "embedded_host",
) -> dict[str, Any]:
    """Create or update a node through Grapher's canonical mutation boundary.

    Unlike legacy host helpers, this surface exposes the complete projection fields
    needed by an encapsulating control system while keeping storage, truth policy,
    semantic integrity, transition handling, and history inside Grapher.
    """
    graph_path = graph_path.expanduser().resolve()
    before = load_graph(graph_path, normalize=False)
    graph = load_graph(graph_path)
    edge_count_before = len(before.get("edges") or [])
    node = G.add_node(
        graph,
        type=type,
        title=title,
        content=content,
        id=node_id,
        path=path,
        tags=tags,
        meta=meta,
        stage=stage,
        status=status,
        workflow_state=workflow_state,
        verification=verification,
        evidence=evidence,
        source_refs=source_refs,
        owners=owners,
        scope=scope,
        provenance=provenance,
        finalized_at=finalized_at,
    )
    existing = before.get("nodes", {}).get(node["id"])
    action = "node_created" if existing is None else "node_updated"
    if existing is not None and existing == graph["nodes"][node["id"]] and len(graph.get("edges") or []) > edge_count_before:
        action = "relationship_created"
    save_graph_mutation(
        graph_path,
        graph,
        action=action,
        target=node["id"],
        before=before,
        **_history_kwargs(
            source=source,
            scope=scope,
            provenance=provenance,
            actor=actor,
            reason=reason,
            evidence_refs=evidence_refs,
            decision_ids=decision_ids,
            requirement_ids=requirement_ids,
            supersedes=supersedes,
            overrides=overrides,
            operation_id=operation_id,
            phase=phase,
        ),
    )
    return node


__all__ = [
    "IntegrationError",
    "apply_delta",
    "contribute_context",
    "export_delta",
    "get_context",
    "infer_links_context",
    "ingest_context",
    "init_context",
    "link_context",
    "list_feedback",
    "neighbors_context",
    "query_context",
    "reindex_context",
]
