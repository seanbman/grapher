"""Graph CRUD and traversal."""

from __future__ import annotations

from collections import deque
from typing import Any

from grapher.model import make_edge, make_id, make_node


class GraphError(Exception):
    pass


_FINALIZED_MUTABLE_FIELDS = frozenset({"updated_at"})


def is_finalized(node: dict[str, Any] | None) -> bool:
    return bool((node or {}).get("finalized_at"))


def finalized_field_changes(
    existing: dict[str, Any],
    candidate: dict[str, Any],
) -> list[str]:
    return sorted(
        field
        for field in (set(existing) | set(candidate))
        if field not in _FINALIZED_MUTABLE_FIELDS
        and existing.get(field) != candidate.get(field)
    )


def assert_not_finalized(
    node: dict[str, Any],
    *,
    node_id: str | None = None,
    operation: str = "mutate",
) -> None:
    if is_finalized(node):
        raise GraphError(
            f"node {node_id or node.get('id')!r} is finalized; cannot {operation}. "
            "Create a correcting record that supersedes, contests, or invalidates it."
        )


def add_node(
    graph: dict[str, Any],
    *,
    type: str,
    title: str,
    content: str = "",
    path: str | None = None,
    tags: list[str] | None = None,
    meta: dict[str, Any] | None = None,
    id: str | None = None,
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
    force_finalized: bool = False,
) -> dict[str, Any]:
    from pathlib import Path

    nodes = graph["nodes"]
    existing = None
    node_id = id

    if node_id:
        existing = nodes.get(node_id)
    elif path:
        want = Path(path).as_posix()
        for n in nodes.values():
            p = n.get("path")
            if p and Path(p).as_posix() == want:
                existing = n
                node_id = n["id"]
                break

    if not node_id:
        node_id = make_id(title)
        existing = nodes.get(node_id)
        if existing:
            node_id = make_id(title)
            existing = None

    # Preserve fields on upsert when caller omits them
    if existing:
        if not title:
            title = existing.get("title") or title
        if tags is None:
            tags = list(existing.get("tags") or [])
        if path is None:
            path = existing.get("path")

    node = make_node(
        id=node_id,
        type=type,
        title=title,
        content=content if content is not None else (existing or {}).get("content", ""),
        path=path,
        tags=tags,
        meta=meta,
        existing=existing,
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
    if existing and is_finalized(existing) and not force_finalized:
        changed = finalized_field_changes(existing, node)
        if changed:
            raise GraphError(
                f"node {node_id!r} is finalized; immutable fields changed: {', '.join(changed)}. "
                "Create a correcting node and supersede it, or use the explicit administrative force option."
            )
    nodes[node_id] = node
    return node


def get_node(graph: dict[str, Any], node_id: str) -> dict[str, Any]:
    node = graph["nodes"].get(node_id)
    if not node:
        raise GraphError(f"node not found: {node_id}")
    return node


def adjacent_edges(graph: dict[str, Any], node_id: str) -> list[dict[str, Any]]:
    return [
        e
        for e in graph["edges"]
        if e.get("from") == node_id or e.get("to") == node_id
    ]


def link(
    graph: dict[str, Any],
    *,
    from_id: str,
    to_id: str,
    rel: str,
    note: str | None = None,
) -> dict[str, Any]:
    if from_id not in graph["nodes"]:
        raise GraphError(f"node not found: {from_id}")
    if to_id not in graph["nodes"]:
        raise GraphError(f"node not found: {to_id}")
    existing = edge_get(graph, from_id, to_id, rel)
    if existing:
        return existing
    edge = make_edge(from_id=from_id, to_id=to_id, rel=rel, note=note)
    graph["edges"].append(edge)
    return edge


def edge_get(
    graph: dict[str, Any],
    from_id: str,
    to_id: str,
    rel: str,
) -> dict[str, Any] | None:
    for e in graph.get("edges") or []:
        if e.get("from") == from_id and e.get("to") == to_id and e.get("rel") == rel:
            return e
    return None


def edge_exists(graph: dict[str, Any], from_id: str, to_id: str, rel: str) -> bool:
    return edge_get(graph, from_id, to_id, rel) is not None


def dedupe_edges(graph: dict[str, Any]) -> int:
    """Remove duplicate (from, to, rel) edges. Returns count removed."""
    seen: set[tuple[str, str, str]] = set()
    deduped: list[dict[str, Any]] = []
    removed = 0
    for e in graph.get("edges") or []:
        key = (e.get("from"), e.get("to"), e.get("rel"))
        if key in seen:
            removed += 1
            continue
        seen.add(key)
        deduped.append(e)
    graph["edges"] = deduped
    return removed


def remove_node(graph: dict[str, Any], node_id: str, *, force: bool = False) -> None:
    node = graph["nodes"].get(node_id)
    if node is None:
        raise GraphError(f"node not found: {node_id}")
    if is_finalized(node) and not force:
        raise GraphError(
            f"node {node_id!r} is finalized; ordinary removal is forbidden. "
            "Preserve it and attach a correcting record instead."
        )
    del graph["nodes"][node_id]
    graph["edges"] = [
        e
        for e in graph["edges"]
        if e.get("from") != node_id and e.get("to") != node_id
    ]


def list_nodes(
    graph: dict[str, Any],
    *,
    type: str | None = None,
    tag: str | None = None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for node in graph["nodes"].values():
        if type and node.get("type") != type:
            continue
        if tag and tag not in (node.get("tags") or []):
            continue
        out.append(node)
    out.sort(key=lambda n: (n.get("type") or "", n.get("title") or "", n.get("id")))
    return out


def neighbors(
    graph: dict[str, Any],
    node_id: str,
    *,
    depth: int = 1,
) -> dict[str, Any]:
    if node_id not in graph["nodes"]:
        raise GraphError(f"node not found: {node_id}")
    depth = max(1, min(depth, 3))
    adj: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for e in graph["edges"]:
        a, b = e.get("from"), e.get("to")
        if not a or not b:
            continue
        adj.setdefault(a, []).append((b, e))
        adj.setdefault(b, []).append((a, e))

    seen = {node_id: 0}
    edge_hits: list[dict[str, Any]] = []
    q: deque[str] = deque([node_id])
    while q:
        cur = q.popleft()
        d = seen[cur]
        if d >= depth:
            continue
        for nxt, edge in adj.get(cur, []):
            if nxt not in seen:
                seen[nxt] = d + 1
                q.append(nxt)
                edge_hits.append(edge)
            elif seen[nxt] == d + 1:
                # same layer alternate edge
                if edge not in edge_hits:
                    edge_hits.append(edge)

    nodes = {
        nid: graph["nodes"][nid]
        for nid in seen
        if nid in graph["nodes"]
    }
    return {
        "root": node_id,
        "depth": depth,
        "nodes": nodes,
        "edges": edge_hits,
        "distances": seen,
    }


def shortest_path(
    graph: dict[str, Any],
    a: str,
    b: str,
) -> dict[str, Any]:
    if a not in graph["nodes"]:
        raise GraphError(f"node not found: {a}")
    if b not in graph["nodes"]:
        raise GraphError(f"node not found: {b}")
    if a == b:
        return {"from": a, "to": b, "nodes": [a], "edges": []}

    adj: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for e in graph["edges"]:
        x, y = e.get("from"), e.get("to")
        if not x or not y:
            continue
        adj.setdefault(x, []).append((y, e))
        adj.setdefault(y, []).append((x, e))

    prev: dict[str, tuple[str, dict[str, Any]] | None] = {a: None}
    q: deque[str] = deque([a])
    found = False
    while q:
        cur = q.popleft()
        if cur == b:
            found = True
            break
        for nxt, edge in adj.get(cur, []):
            if nxt in prev:
                continue
            prev[nxt] = (cur, edge)
            q.append(nxt)

    if not found:
        return {"from": a, "to": b, "nodes": [], "edges": [], "found": False}

    node_path: list[str] = []
    edge_path: list[dict[str, Any]] = []
    cur = b
    while cur != a:
        node_path.append(cur)
        parent, edge = prev[cur]  # type: ignore[misc]
        edge_path.append(edge)
        cur = parent
    node_path.append(a)
    node_path.reverse()
    edge_path.reverse()
    return {
        "from": a,
        "to": b,
        "found": True,
        "nodes": node_path,
        "edges": edge_path,
        "node_details": {nid: graph["nodes"][nid] for nid in node_path},
    }


def stats(graph: dict[str, Any], vectors: dict[str, Any] | None = None) -> dict[str, Any]:
    by_type: dict[str, int] = {}
    by_status: dict[str, int] = {}
    for n in graph["nodes"].values():
        t = n.get("type") or "other"
        by_type[t] = by_type.get(t, 0) + 1
        s = n.get("status") or "unclassified"
        by_status[s] = by_status.get(s, 0) + 1
    by_rel: dict[str, int] = {}
    for e in graph["edges"]:
        r = e.get("rel") or "related"
        by_rel[r] = by_rel.get(r, 0) + 1
    out: dict[str, Any] = {
        "version": graph.get("version", 1),
        "graph": graph.get("graph"),
        "nodes": len(graph["nodes"]),
        "edges": len(graph["edges"]),
        "by_type": dict(sorted(by_type.items())),
        "by_status": dict(sorted(by_status.items())),
        "by_rel": dict(sorted(by_rel.items())),
    }
    if vectors is not None:
        vecs = vectors.get("vectors") or {}
        covered = sum(1 for nid in graph["nodes"] if nid in vecs)
        out["vectors"] = {
            "model": vectors.get("model"),
            "provider": vectors.get("provider"),
            "dims": vectors.get("dims"),
            "indexed": len(vecs),
            "coverage": covered,
            "nodes": len(graph["nodes"]),
        }
    return out


def to_mermaid(graph: dict[str, Any]) -> str:
    lines = ["flowchart LR"]
    for nid, node in graph["nodes"].items():
        label = (node.get("title") or nid).replace('"', "'")
        safe = nid.replace("-", "_")
        lines.append(f'  {safe}["{label}"]')
    for e in graph["edges"]:
        a = str(e.get("from", "")).replace("-", "_")
        b = str(e.get("to", "")).replace("-", "_")
        rel = (e.get("rel") or "related").replace('"', "'")
        lines.append(f'  {a} -->|{rel}| {b}')
    return "\n".join(lines) + "\n"
