"""Checkpoint nodes for consolidated project snapshots."""

from __future__ import annotations

import json
from typing import Any

from grapher.graph import add_node, assert_not_finalized, get_node
from grapher.model import make_edge, now_iso
from grapher.registry import TRUTH_STATUSES


def _checkpoint_dir(graph_path) -> Any:
    from pathlib import Path

    return Path(graph_path).parent / "checkpoints"


def create_checkpoint(
    graph: dict[str, Any],
    graph_path,
    *,
    title: str,
    content: str = "",
    node_ids: list[str] | None = None,
    status: str = "current",
    dry_run: bool = False,
) -> dict[str, Any]:
    if status not in TRUTH_STATUSES:
        raise ValueError(f"unknown status {status!r}")

    ts = now_iso()
    ck_id = f"checkpoint-{ts.replace(':', '').replace('+', '')}"

    if node_ids:
        for nid in node_ids:
            get_node(graph, nid)

    preview = {
        "action": "checkpoint_create",
        "id": ck_id,
        "title": title,
        "derived_from": node_ids or [],
        "dry_run": dry_run,
    }
    if dry_run:
        return preview

    node = add_node(
        graph,
        type="checkpoint",
        title=title,
        content=content,
        id=ck_id,
        status=status,
        stage="maintaining",
    )

    for nid in node_ids or []:
        graph["edges"].append(
            make_edge(from_id=ck_id, to_id=nid, rel="derived_from", note="checkpoint")
        )

    ck_dir = _checkpoint_dir(graph_path)
    ck_dir.mkdir(parents=True, exist_ok=True)
    snapshot = {
        "checkpoint_id": ck_id,
        "created_at": ts,
        "title": title,
        "node_ids": node_ids or list(graph["nodes"].keys()),
        "graph_version": graph.get("version", 1),
    }
    snap_path = ck_dir / f"{ck_id}.json"
    snap_path.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")

    preview["node"] = node
    preview["snapshot"] = str(snap_path)
    return preview


def list_checkpoints(graph_path) -> dict[str, Any]:
    ck_dir = _checkpoint_dir(graph_path)
    if not ck_dir.is_dir():
        return {"checkpoints": [], "count": 0}
    items = []
    for p in sorted(ck_dir.glob("checkpoint-*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            data["path"] = str(p)
            items.append(data)
        except (json.JSONDecodeError, OSError):
            continue
    return {"checkpoints": items, "count": len(items)}


def refresh_checkpoint(
    graph: dict[str, Any],
    graph_path,
    checkpoint_id: str,
    *,
    dry_run: bool = False,
    yes: bool = False,
) -> dict[str, Any]:
    node = get_node(graph, checkpoint_id)
    if node.get("type") != "checkpoint":
        raise ValueError(f"node {checkpoint_id!r} is not a checkpoint")
    assert_not_finalized(node, node_id=checkpoint_id, operation="refresh checkpoint")

    derived = [
        e["to"]
        for e in graph.get("edges") or []
        if e.get("from") == checkpoint_id and e.get("rel") == "derived_from"
    ]

    changed_sources = [nid for nid in derived if (graph["nodes"].get(nid) or {}).get("updated_at", "") > node.get("updated_at", "")]
    checkpoint_generation = (node.get("scope") or {}).get("generation_id")
    current_sources = []
    for nid in derived:
        source = graph["nodes"].get(nid) or {}
        source_generation = (source.get("scope") or {}).get("generation_id")
        if checkpoint_generation and source_generation and source_generation != checkpoint_generation:
            continue
        if source.get("status") in ("superseded", "rejected", "deprecated"):
            continue
        if (source.get("provenance") or {}).get("integrity") == "invalidated":
            continue
        current_sources.append(source)
    proposed_content = "\n".join(
        f"- {source.get('title') or source.get('id')}: {(source.get('content') or '').strip()}"
        for source in current_sources
    )
    contradictions = [e for e in graph.get("edges") or [] if e.get("rel") == "contradicts" and (e.get("from") in derived or e.get("to") in derived)]
    preview = {
        "action": "checkpoint_refresh",
        "id": checkpoint_id,
        "derived_from": derived,
        "dry_run": dry_run,
        "diff": {"changed_sources": changed_sources,
                 "content_changed": proposed_content != (node.get("content") or ""),
                 "before": node.get("content") or "", "after": proposed_content},
        "contradictions": contradictions,
    }
    if dry_run:
        return preview
    if not yes:
        raise ValueError("checkpoint refresh requires --yes after reviewing --dry-run")
    if contradictions:
        raise ValueError("checkpoint has unresolved contradictions; curate them before refresh")

    node["content"] = proposed_content
    node["updated_at"] = now_iso()
    ck_dir = _checkpoint_dir(graph_path)
    ck_dir.mkdir(parents=True, exist_ok=True)
    snap_path = ck_dir / f"{checkpoint_id}.json"
    snapshot = {
        "checkpoint_id": checkpoint_id,
        "refreshed_at": now_iso(),
        "title": node.get("title"),
        "node_ids": derived,
        "graph_version": graph.get("version", 1),
    }
    snap_path.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    preview["snapshot"] = str(snap_path)
    return preview
