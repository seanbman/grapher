"""Build Plotly 3D figures from the knowledge graph."""

from __future__ import annotations

import json
from typing import Any

from grapher.query import superseded_by, supersedes_targets
from grapher.viz.adapter import (
    TYPE_COLORS,
    filter_edges,
    filter_nodes,
    node_color,
)
from grapher.viz.layout3d import compute_layout


def _is_pending(node: dict[str, Any]) -> bool:
    meta = node.get("meta") or {}
    if meta.get("status") == "pending":
        return True
    return not (node.get("content") or "").strip()


def build_figure(
    graph: dict[str, Any],
    *,
    positions: dict[str, tuple[float, float, float]] | None = None,
    types: list[str] | None = None,
    search: str = "",
    pending_only: bool = False,
    status: str | None = None,
    stage: str | None = None,
    verification: str | None = None,
    project: str | None = None,
    mission: str | None = None,
    generation: str | None = None,
    selected_id: str | None = None,
    view_mode: str = "knowledge",
    encode: str = "type",
    exclude_superseded: bool = False,
    current_only: bool = False,
) -> Any:
    try:
        import plotly.graph_objects as go
    except ImportError as e:
        raise ImportError(
            "dashboard requires plotly; install with: pip install 'grapher[dash]'"
        ) from e

    nodes_map: dict[str, Any] = dict(graph.get("nodes") or {})
    if not nodes_map:
        fig = go.Figure()
        fig.update_layout(
            title="Empty graph — run: grapher ingest <DIR>",
            scene=dict(
                xaxis=dict(visible=False),
                yaxis=dict(visible=False),
                zaxis=dict(visible=False),
            ),
            margin=dict(l=0, r=0, t=40, b=0),
            paper_bgcolor="#0f1115",
            font=dict(color="#e8eaed"),
        )
        return fig

    if positions is None:
        positions = compute_layout(graph, view_mode=view_mode)

    visible = filter_nodes(
        graph,
        types=types,
        search=search,
        pending_only=pending_only, status=status, stage=stage,
        verification=verification, project=project, mission=mission, generation=generation,
        exclude_superseded=exclude_superseded,
        current_only=current_only,
        view_mode=view_mode,
    )
    visible_ids = sorted(visible)
    search_q = (search or "").strip()
    matched = visible if not search_q else {
        nid for nid in visible_ids
        if search_q.lower() in " ".join([
            str(nodes_map[nid].get("title") or ""),
            str(nodes_map[nid].get("content") or ""),
        ]).lower()
    }

    edge_x: list[float | None] = []
    edge_y: list[float | None] = []
    edge_z: list[float | None] = []
    for e in filter_edges(graph, visible, view_mode=view_mode):
        a, b = e.get("from"), e.get("to")
        if a not in positions or b not in positions:
            continue
        x0, y0, z0 = positions[a]
        x1, y1, z1 = positions[b]
        edge_x += [x0, x1, None]
        edge_y += [y0, y1, None]
        edge_z += [z0, z1, None]

    edge_trace = go.Scatter3d(
        x=edge_x,
        y=edge_y,
        z=edge_z,
        mode="lines",
        line=dict(color="rgba(160,160,170,0.35)", width=3),
        hoverinfo="none",
        name="edges",
    )

    xs, ys, zs = [], [], []
    colors, sizes, texts, custom = [], [], [], []
    for nid in visible_ids:
        node = nodes_map[nid]
        x, y, z = positions.get(nid, (0.0, 0.0, 0.0))
        xs.append(x)
        ys.append(y)
        zs.append(z)
        colors.append(node_color(node, encode=encode))
        content_len = len((node.get("content") or "").strip())
        size = 8 + min(10, content_len // 40)
        if nid == selected_id:
            size += 6
        if search_q and nid not in matched:
            size = max(5, size - 3)
        sizes.append(size)
        title = node.get("title") or nid
        status = node.get("status") or "unclassified"
        texts.append(
            f"<b>{title}</b><br>type: {node.get('type')}<br>status: {status}<br>id: {nid}"
        )
        custom.append(nid)

    if search_q:
        hi_idx = [i for i, nid in enumerate(visible_ids) if nid in matched]
        lo_idx = [i for i, nid in enumerate(visible_ids) if nid not in matched]
    else:
        hi_idx = list(range(len(visible_ids)))
        lo_idx = []

    def _trace(idxs: list[int], opacity: float, name: str) -> Any:
        if not idxs:
            return None
        return go.Scatter3d(
            x=[xs[i] for i in idxs],
            y=[ys[i] for i in idxs],
            z=[zs[i] for i in idxs],
            mode="markers",
            marker=dict(
                size=[sizes[i] for i in idxs],
                color=[colors[i] for i in idxs],
                opacity=opacity,
                line=dict(width=1, color="rgba(255,255,255,0.25)"),
            ),
            text=[texts[i] for i in idxs],
            hoverinfo="text",
            customdata=[custom[i] for i in idxs],
            name=name,
        )

    traces = [edge_trace]
    node_lo = _trace(lo_idx, 0.2, "dimmed")
    node_hi = _trace(hi_idx, 0.95, "nodes")
    if node_lo is not None:
        traces.append(node_lo)
    if node_hi is not None:
        traces.append(node_hi)

    meta = graph.get("graph") or {}
    title = meta.get("name") or "grapher"
    fig = go.Figure(data=traces)
    fig.update_layout(
        title=f"{title} — {view_mode}",
        showlegend=False,
        margin=dict(l=0, r=0, t=30, b=0),
        paper_bgcolor="#0f1115",
        plot_bgcolor="#0f1115",
        font=dict(color="#e8eaed", family="IBM Plex Sans, Segoe UI, sans-serif"),
        scene=dict(
            xaxis=dict(showticklabels=False, title="", showgrid=False, zeroline=False, showbackground=False),
            yaxis=dict(showticklabels=False, title="", showgrid=False, zeroline=False, showbackground=False),
            zaxis=dict(showticklabels=False, title="", showgrid=False, zeroline=False, showbackground=False),
            bgcolor="#0f1115",
            aspectmode="data",
        ),
        uirevision="grapher-keep-camera",
    )
    return fig


def node_detail_markdown(graph: dict[str, Any], node_id: str | None) -> str:
    if not node_id:
        return "_Click a node to inspect it._"
    node = (graph.get("nodes") or {}).get(node_id)
    if not node:
        return f"_Node not found: `{node_id}`_"

    tags = ", ".join(f"`{t}`" for t in (node.get("tags") or [])) or "—"
    truth_status = node.get("status") or "unclassified"
    ingest_status = (node.get("meta") or {}).get("status")
    path = node.get("path") or "—"
    content = (node.get("content") or "").strip() or "_(empty — needs enrichment)_"
    stage = node.get("stage")
    if isinstance(stage, list):
        stage_str = ", ".join(stage)
    else:
        stage_str = stage or "—"

    lines = [
        f"### {node.get('title') or node_id}",
        f"**id:** `{node_id}`  ",
        f"**type:** `{node.get('type')}`  ",
        f"**status:** `{truth_status}`  ",
        f"**workflow:** `{node.get('workflow_state') or 'not_applicable'}`  ",
        f"**verification:** `{node.get('verification') or 'unverified'}`  ",
        f"**stage:** `{stage_str}`  ",
        f"**path:** `{path}`  ",
        f"**tags:** {tags}",
        f"**owners:** {', '.join(node.get('owners') or []) or '—'}  ",
        f"**source refs:** {', '.join(node.get('source_refs') or []) or '—'}  ",
        f"**scope:** {json.dumps(node.get('scope') or {}, sort_keys=True)}  ",
        f"**provenance:** {json.dumps(node.get('provenance') or {}, sort_keys=True)}  ",
        f"**evidence:** {json.dumps(node.get('evidence') or [], sort_keys=True)}  ",
        f"**created:** {node.get('created_at') or '—'}  ",
        f"**updated:** {node.get('updated_at') or '—'}  ",
        f"**started / due / completed:** {node.get('started_at') or '—'} / {node.get('due_at') or '—'} / {node.get('completed_at') or '—'}  ",
        f"**finalized:** {node.get('finalized_at') or '—'}  ",
    ]
    if ingest_status == "pending":
        lines.append(f"**ingest:** `pending`  ")

    superseded = superseded_by(graph, node_id)
    supersedes = supersedes_targets(graph, node_id)
    if superseded:
        lines.append(f"**superseded by:** {', '.join(f'`{x}`' for x in superseded)}  ")
    if supersedes:
        lines.append(f"**supersedes:** {', '.join(f'`{x}`' for x in supersedes)}  ")

    lines.extend(["", "#### Content", content, "", "#### Edges"])

    edges = [
        e
        for e in (graph.get("edges") or [])
        if e.get("from") == node_id or e.get("to") == node_id
    ]
    if not edges:
        lines.append("_No edges._")
    else:
        nodes = graph.get("nodes") or {}
        for e in edges:
            other = e.get("to") if e.get("from") == node_id else e.get("from")
            other_title = (nodes.get(other) or {}).get("title") or other
            direction = "→" if e.get("from") == node_id else "←"
            lines.append(
                f"- `{e.get('from')}` --**{e.get('rel')}**--> `{e.get('to')}`  "
                f"({direction} {other_title})"
            )
    return "\n".join(lines)
