"""Stable grapher API surface for agent-hub and similar daemons."""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from grapher import graph as G
from grapher import search as S
from grapher.ingest import ingest_directory
from grapher.linking import infer_from_config
from grapher.store import init_store, load_graph, save_graph_mutation
from grapher.transfer import merge_graph


class IntegrationError(Exception):
    pass


def _actor_from_provenance(provenance: dict[str, Any] | None) -> dict[str, Any] | None:
    if not provenance:
        return None
    actor = {
        "id": provenance.get("actor_id"),
        "kind": provenance.get("actor_kind"),
        "role": provenance.get("actor_role"),
        "session_id": provenance.get("session_id"),
        "source": provenance.get("source"),
    }
    actor = {key: value for key, value in actor.items() if value is not None}
    return actor or None


def _history_kwargs(
    *,
    source: str,
    scope: dict[str, Any] | None = None,
    provenance: dict[str, Any] | None = None,
    actor: dict[str, Any] | None = None,
    reason: str | None = None,
    evidence_refs: list[str] | None = None,
    decision_ids: list[str] | None = None,
    requirement_ids: list[str] | None = None,
    supersedes: list[str] | None = None,
    overrides: list[str] | None = None,
    operation_id: str | None = None,
    phase: str = "executed",
    extra_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    context: dict[str, Any] = {}
    if scope:
        context["scope"] = scope
    if provenance:
        context["provenance"] = provenance
    if extra_context:
        context.update(extra_context)
    return {
        "source": source,
        "context": context or None,
        "actor": actor or _actor_from_provenance(provenance),
        "reason": reason,
        "evidence_refs": evidence_refs,
        "decision_ids": decision_ids,
        "requirement_ids": requirement_ids,
        "supersedes": supersedes,
        "overrides": overrides,
        "operation_id": operation_id,
        "phase": phase,
    }


def init_context(
    graph_path: Path,
    *,
    scope: str = "project",
    name: str | None = None,
    domain: str | None = None,
) -> Path:
    """Initialize a hub or project grapher context with sensible defaults."""
    graph_path = graph_path.expanduser().resolve()
    if scope == "hub":
        domain = domain or "operations"
        kinds = ["knowledge", "operations"]
        profile = "operations"
        graph_name = name or "agent-hub"
    else:
        domain = domain or "software"
        kinds = ["knowledge", "implementation", "decision"]
        profile = "software"
        graph_name = name or graph_path.parent.name

    init_store(
        graph_path,
        name=graph_name,
        domain=domain,
        kinds=kinds,
        profile=profile,
    )
    return graph_path


def query_context(
    graph_path: Path,
    text: str,
    *,
    limit: int = 10,
    type: str | None = None,
    tag: str | None = None,
    exclude_superseded: bool = True,
    mode: str = "hybrid",
    project: str | None = None, mission: str | None = None,
    generation: str | None = None, actor: str | None = None, role: str | None = None,
) -> list[dict[str, Any]]:
    """Search a context graph. Uses hybrid search with lexical fallback."""
    graph_path = graph_path.expanduser().resolve()
    graph = load_graph(graph_path)
    try:
        return S.search(
            graph,
            graph_path,
            text,
            mode=mode,
            type=type,
            tag=tag,
            limit=limit,
            exclude_superseded=exclude_superseded, project=project, mission=mission,
            generation=generation, actor=actor, role=role,
        )
    except Exception:
        return S.lexical_search(
            graph,
            text,
            type=type,
            tag=tag,
            limit=limit,
            exclude_superseded=exclude_superseded,
            graph_path=graph_path, project=project, mission=mission,
            generation=generation, actor=actor, role=role,
        )


def contribute_context(
    graph_path: Path,
    *,
    type: str,
    title: str,
    content: str = "",
    node_id: str | None = None,
    path: str | None = None,
    tags: list[str] | None = None,
    edges: list[dict[str, Any]] | None = None,
    status: str | None = None,
    workflow_state: str | None = None, verification: str | None = None,
    evidence: list[dict[str, Any]] | None = None, scope: dict[str, Any] | None = None,
    provenance: dict[str, Any] | None = None, finalized_at: str | None = None,
    actor: dict[str, Any] | None = None,
    reason: str | None = None,
    evidence_refs: list[str] | None = None,
    decision_ids: list[str] | None = None,
    requirement_ids: list[str] | None = None,
    supersedes: list[str] | None = None,
    overrides: list[str] | None = None,
    operation_id: str | None = None,
    phase: str = "executed",
    source: str = "agent_hub",
) -> dict[str, Any]:
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
        status=status, workflow_state=workflow_state, verification=verification,
        evidence=evidence, scope=scope, provenance=provenance, finalized_at=finalized_at,
    )
    existing = before.get("nodes", {}).get(node["id"])
    for edge in edges or []:
        G.link(
            graph,
            from_id=edge["from_id"],
            to_id=edge["to_id"],
            rel=edge["rel"],
            note=edge.get("note"),
        )
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


def export_delta(graph_path: Path, since_ts: str | None = None) -> dict[str, Any]:
    graph_path = graph_path.expanduser().resolve()
    graph = load_graph(graph_path)
    nodes: dict[str, Any] = {}
    edges: list[dict[str, Any]] = []
    since = _parse_ts(since_ts) if since_ts else None
    for nid, node in graph.get("nodes", {}).items():
        updated = _parse_ts(node.get("updated_at") or node.get("created_at"))
        if since is None or (updated and updated >= since):
            nodes[nid] = copy.deepcopy(node)
    node_ids = set(nodes)
    for edge in graph.get("edges", []):
        if edge.get("from") in node_ids or edge.get("to") in node_ids:
            edges.append(copy.deepcopy(edge))
    return {
        "version": graph.get("version", 2),
        "graph": graph.get("graph"),
        "nodes": nodes,
        "edges": edges,
    }


def apply_delta(
    graph_path: Path,
    incoming: dict[str, Any],
    *,
    actor: dict[str, Any] | None = None,
    reason: str | None = None,
    operation_id: str | None = None,
    phase: str = "executed",
    source: str = "agent_hub",
) -> dict[str, Any]:
    graph_path = graph_path.expanduser().resolve()
    before = load_graph(graph_path, normalize=False)
    local = load_graph(graph_path)
    result = merge_graph(local, incoming)
    save_graph_mutation(
        graph_path,
        result["graph"],
        action="delta_applied",
        before=before,
        source=source,
        actor=actor,
        reason=reason,
        operation_id=operation_id,
        phase=phase,
    )
    return {
        "nodes_added": result["nodes_added"],
        "nodes_updated": result["nodes_updated"],
        "edges_added": result["edges_added"],
    }


def list_feedback(graph_path: Path, *, limit: int = 20) -> list[dict[str, Any]]:
    graph_path = graph_path.expanduser().resolve()
    graph = load_graph(graph_path)
    items: list[tuple[str, dict[str, Any]]] = []
    for node in graph.get("nodes", {}).values():
        tags = node.get("tags") or []
        if "feedback" in tags or "resident-inbox" in tags:
            items.append((node.get("updated_at") or node.get("created_at") or "", node))
    items.sort(key=lambda x: x[0], reverse=True)
    return [n for _, n in items[:limit]]


def get_context(graph_path: Path, node_id: str) -> dict[str, Any]:
    graph_path = graph_path.expanduser().resolve()
    graph = load_graph(graph_path)
    try:
        node = G.get_node(graph, node_id)
    except G.GraphError as exc:
        raise IntegrationError(str(exc)) from exc
    return {"node": node, "edges": G.adjacent_edges(graph, node_id)}


def neighbors_context(
    graph_path: Path,
    node_id: str,
    *,
    depth: int = 1,
) -> dict[str, Any]:
    graph_path = graph_path.expanduser().resolve()
    graph = load_graph(graph_path)
    try:
        return G.neighbors(graph, node_id, depth=depth)
    except G.GraphError as exc:
        raise IntegrationError(str(exc)) from exc


def link_context(
    graph_path: Path,
    from_id: str,
    to_id: str,
    rel: str,
    *,
    note: str | None = None,
    scope: dict[str, Any] | None = None,
    provenance: dict[str, Any] | None = None,
    actor: dict[str, Any] | None = None,
    reason: str | None = None,
    evidence_refs: list[str] | None = None,
    decision_ids: list[str] | None = None,
    requirement_ids: list[str] | None = None,
    supersedes: list[str] | None = None,
    overrides: list[str] | None = None,
    operation_id: str | None = None,
    phase: str = "executed",
    source: str = "agent_hub",
) -> dict[str, Any]:
    graph_path = graph_path.expanduser().resolve()
    before = load_graph(graph_path, normalize=False)
    graph = load_graph(graph_path)
    existed = G.edge_get(graph, from_id, to_id, rel) is not None
    try:
        edge = G.link(graph, from_id=from_id, to_id=to_id, rel=rel, note=note)
    except G.GraphError as exc:
        raise IntegrationError(str(exc)) from exc
    if not existed:
        save_graph_mutation(
            graph_path,
            graph,
            action="relationship_created",
            before=before,
            target=f"{from_id}:{rel}:{to_id}",
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
    return edge


def ingest_context(
    graph_path: Path,
    directory: Path | str,
    *,
    glob: str | None = None,
    types: set[str] | None = None,
    max_files: int = 5000,
    create_stubs: bool = True,
    scope: dict[str, Any] | None = None,
    provenance: dict[str, Any] | None = None,
    actor: dict[str, Any] | None = None,
    reason: str | None = None,
    evidence_refs: list[str] | None = None,
    decision_ids: list[str] | None = None,
    requirement_ids: list[str] | None = None,
    supersedes: list[str] | None = None,
    overrides: list[str] | None = None,
    operation_id: str | None = None,
    phase: str = "executed",
    source: str = "agent_hub",
) -> dict[str, Any]:
    graph_path = graph_path.expanduser().resolve()
    before = load_graph(graph_path, normalize=False)
    graph = load_graph(graph_path)
    result = ingest_directory(
        graph,
        Path(directory),
        graph_path=graph_path,
        glob=glob,
        types=types,
        max_files=max_files,
        create_stubs=create_stubs,
    )
    if result.get("created_stubs", 0):
        save_graph_mutation(
            graph_path,
            graph,
            action="ingest_queued",
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
                extra_context={"directory": str(Path(directory).resolve()), "created_stubs": result.get("created_stubs", 0)},
            ),
        )
    return result


def reindex_context(graph_path: Path) -> dict[str, Any]:
    graph_path = graph_path.expanduser().resolve()
    graph = load_graph(graph_path)
    return S.reindex(graph, graph_path)


def infer_links_context(
    graph_path: Path,
    *,
    dry_run: bool = False,
    scope: dict[str, Any] | None = None,
    provenance: dict[str, Any] | None = None,
    actor: dict[str, Any] | None = None,
    reason: str | None = None,
    evidence_refs: list[str] | None = None,
    decision_ids: list[str] | None = None,
    requirement_ids: list[str] | None = None,
    supersedes: list[str] | None = None,
    overrides: list[str] | None = None,
    operation_id: str | None = None,
    phase: str = "executed",
    source: str = "agent_hub",
) -> dict[str, Any]:
    graph_path = graph_path.expanduser().resolve()
    before = load_graph(graph_path, normalize=False)
    graph = load_graph(graph_path)
    result = infer_from_config(graph, graph_path, dry_run=dry_run)
    if not dry_run and result.get("proposed", 0):
        save_graph_mutation(
            graph_path,
            graph,
            action="curation_applied",
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
                extra_context={"kind": "infer_links"},
            ),
        )
    return result


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
