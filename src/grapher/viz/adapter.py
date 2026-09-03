"""Adapt graph data for Dash views, filters, and encoding."""

from __future__ import annotations

from typing import Any

from grapher.query import matches_filters, parse_stage_filter, parse_status_filter
from grapher.registry import VIEW_MODE_LABELS, VIEW_MODES, VIEW_RELATIONS


STATUS_COLORS = {
    "current": "#54A24B",
    "canonical_spec": "#4C78A8",
    "proposed": "#F58518",
    "unclassified": "#BAB0AC",
    "historical": "#9D755D",
    "superseded": "#E45756",
    "deprecated": "#B279A2",
    "rejected": "#FF9DA6",
}

TYPE_COLORS = {
    "document": "#4C78A8",
    "image": "#F58518",
    "video": "#EECA3B",
    "audio": "#B279A2",
    "instruction": "#54A24B",
    "finding": "#E45756",
    "concept": "#72B7B2",
    "command": "#FF9DA6",
    "session": "#9D755D",
    "checkpoint": "#9C755F",
    "decision": "#636EFA",
    "requirement": "#EF553B",
    "artifact": "#00CC96",
    "component": "#B07AA1",
    "milestone": "#F2CF5B",
    "idea": "#72B7B2",
    "issue": "#E45756",
    "other": "#BAB0AC",
}


def filter_nodes(
    graph: dict[str, Any],
    *,
    types: list[str] | None = None,
    search: str = "",
    status: str | None = None,
    stage: str | None = None,
    verification: str | None = None,
    project: str | None = None,
    mission: str | None = None,
    generation: str | None = None,
    pending_only: bool = False,
    exclude_superseded: bool = False,
    current_only: bool = False,
    view_mode: str = "knowledge",
) -> set[str]:
    nodes = graph.get("nodes") or {}
    type_set = set(types) if types else None
    status_set = parse_status_filter(status)
    stage_set = parse_stage_filter(stage)
    rels = VIEW_RELATIONS.get(view_mode, VIEW_RELATIONS["knowledge"])

    visible: set[str] = set()
    for nid, node in nodes.items():
        if type_set and node.get("type") not in type_set:
            continue
        if pending_only and not _is_pending(node):
            continue
        if not matches_filters(
            node,
            status=status_set,
            stage=stage_set, verification=verification,
            project=project, mission=mission, generation=generation,
            exclude_superseded=exclude_superseded,
            current_only=current_only,
        ):
            continue
        if search.strip() and not _node_matches_search(node, search):
            continue
        visible.add(nid)

    if view_mode != "knowledge" and not any((project, mission, generation, status, stage, verification)):
        # Include nodes connected by emphasized relations
        edge_nodes = set(visible)
        for e in graph.get("edges") or []:
            rel = e.get("rel")
            if rel not in rels:
                continue
            a, b = e.get("from"), e.get("to")
            if a in edge_nodes or b in edge_nodes:
                if a in nodes:
                    visible.add(a)
                if b in nodes:
                    visible.add(b)

    return visible


def filter_edges(
    graph: dict[str, Any],
    visible: set[str],
    *,
    view_mode: str = "knowledge",
) -> list[dict[str, Any]]:
    rels = VIEW_RELATIONS.get(view_mode)
    out: list[dict[str, Any]] = []
    for e in graph.get("edges") or []:
        a, b = e.get("from"), e.get("to")
        if a not in visible or b not in visible:
            continue
        if rels and e.get("rel") not in rels:
            continue
        out.append(e)
    return out


def node_color(node: dict[str, Any], *, encode: str = "type") -> str:
    if encode == "status":
        status = (node.get("status") or "unclassified").lower()
        return STATUS_COLORS.get(status, STATUS_COLORS["unclassified"])
    ntype = node.get("type") or "other"
    return TYPE_COLORS.get(ntype, TYPE_COLORS["other"])


def graph_summary(graph: dict[str, Any]) -> dict[str, Any]:
    from grapher.audit import audit_graph
    meta = graph.get("graph") or {}
    nodes = graph.get("nodes") or {}
    edges = graph.get("edges") or []
    return {
        "name": meta.get("name"),
        "domain": meta.get("domain"),
        "kinds": meta.get("kinds"),
        "stages": meta.get("stages"),
        "profile": meta.get("profile"),
        "version": graph.get("version", 1),
        "nodes": len(nodes),
        "edges": len(edges),
        "health": audit_graph(graph)["health"],
    }


def _is_pending(node: dict[str, Any]) -> bool:
    meta = node.get("meta") or {}
    if meta.get("status") == "pending":
        return True
    return not (node.get("content") or "").strip()


def _node_matches_search(node: dict[str, Any], query: str) -> bool:
    q = query.strip().lower()
    if not q:
        return True
    hay = " ".join(
        [
            str(node.get("title") or ""),
            str(node.get("content") or ""),
            str(node.get("path") or ""),
            str(node.get("status") or ""),
            " ".join(str(t) for t in (node.get("tags") or [])),
            str(node.get("id") or ""),
        ]
    ).lower()
    return q in hay


def export_view(
    graph: dict[str, Any], *, format: str = "json", view_mode: str = "knowledge",
    types: list[str] | None = None, search: str = "", status: str | None = None,
    stage: str | None = None, verification: str | None = None,
    generation: str | None = None,
) -> tuple[str, str]:
    """Serialize a filtered, explicitly non-canonical dashboard subgraph."""
    import csv
    import io
    import json
    from datetime import datetime, timezone

    visible = filter_nodes(graph, types=types, search=search, status=status, stage=stage,
                           verification=verification, generation=generation, view_mode=view_mode)
    nodes = {nid: node for nid, node in (graph.get("nodes") or {}).items() if nid in visible}
    edges = filter_edges(graph, visible, view_mode=view_mode)
    meta = {"export_kind": "filtered_view_subgraph", "canonical": False,
            "graph_name": (graph.get("graph") or {}).get("name"),
            "schema_version": graph.get("version", 1),
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "view": view_mode,
            "filters": {"types": types or [], "search": search, "status": status,
                        "stage": stage, "verification": verification, "generation": generation}}
    if format == "json":
        return json.dumps({"export": meta, "nodes": nodes, "edges": edges}, indent=2, ensure_ascii=False) + "\n", "grapher-view.json"
    output = io.StringIO()
    if format == "nodes-csv":
        fields = ["id", "type", "title", "status", "workflow_state", "verification", "stage", "scope", "provenance", "path"]
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        for node in nodes.values():
            writer.writerow({field: json.dumps(node.get(field), ensure_ascii=False) if field in ("stage", "scope", "provenance") else node.get(field) for field in fields})
        return output.getvalue(), "grapher-nodes.csv"
    if format == "edges-csv":
        fields = ["from", "to", "rel", "note", "created_at"]
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        for edge in edges:
            writer.writerow({field: edge.get(field) for field in fields})
        return output.getvalue(), "grapher-edges.csv"
    raise ValueError(f"unsupported dashboard export format {format!r}")
