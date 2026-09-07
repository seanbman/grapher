"""Checkpoint nodes for consolidated project snapshots."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

from grapher.graph import add_node, assert_not_finalized, get_node
from grapher.model import make_edge, now_iso
from grapher.registry import TRUTH_STATUSES


def _checkpoint_dir(graph_path) -> Any:
    from pathlib import Path

    return Path(graph_path).parent / "checkpoints"


def _node_hash(node: dict[str, Any]) -> str:
    payload = json.dumps(node, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _snapshot_payload(
    graph: dict[str, Any],
    *,
    checkpoint_id: str,
    title: str,
    node_ids: list[str],
    timestamp_key: str,
    timestamp: str,
) -> dict[str, Any]:
    nodes = {
        nid: deepcopy(graph["nodes"][nid])
        for nid in node_ids
        if nid in (graph.get("nodes") or {})
    }
    return {
        "checkpoint_id": checkpoint_id,
        timestamp_key: timestamp,
        "title": title,
        "node_ids": node_ids,
        "graph_version": graph.get("version", 1),
        "source_hashes": {nid: _node_hash(node) for nid, node in nodes.items()},
        "nodes": nodes,
    }


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
    selected_ids = list(node_ids) if node_ids else list((graph.get("nodes") or {}).keys())

    for nid in selected_ids:
        get_node(graph, nid)

    preview = {
        "action": "checkpoint_create",
        "id": ck_id,
        "title": title,
        "derived_from": selected_ids,
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

    for nid in selected_ids:
        graph["edges"].append(
            make_edge(from_id=ck_id, to_id=nid, rel="derived_from", note="checkpoint")
        )

    ck_dir = _checkpoint_dir(graph_path)
    ck_dir.mkdir(parents=True, exist_ok=True)
    snapshot = _snapshot_payload(
        graph,
        checkpoint_id=ck_id,
        title=title,
        node_ids=selected_ids,
        timestamp_key="created_at",
        timestamp=ts,
    )
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

    ck_dir = _checkpoint_dir(graph_path)
    snap_path = ck_dir / f"{checkpoint_id}.json"
    previous_snapshot: dict[str, Any] = {}
    if snap_path.is_file():
        try:
            previous_snapshot = json.loads(snap_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            previous_snapshot = {}
    previous_hashes = previous_snapshot.get("source_hashes") or {}

    missing_sources = [nid for nid in derived if nid not in (graph.get("nodes") or {})]
    current_hashes = {
        nid: _node_hash(graph["nodes"][nid])
        for nid in derived
        if nid in (graph.get("nodes") or {})
    }
    if previous_hashes:
        changed_sources = [
            nid for nid in derived
            if nid in current_hashes and current_hashes.get(nid) != previous_hashes.get(nid)
        ]
    else:
        changed_sources = [
            nid for nid in derived
            if (graph["nodes"].get(nid) or {}).get("updated_at", "") > node.get("updated_at", "")
        ]

    checkpoint_generation = (node.get("scope") or {}).get("generation_id")
    current_sources = []
    for nid in derived:
        source = graph["nodes"].get(nid) or {}
        if not source:
            continue
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
    contradictions = [
        e for e in graph.get("edges") or []
        if e.get("rel") == "contradicts"
        and (e.get("from") in derived or e.get("to") in derived)
    ]
    preview = {
        "action": "checkpoint_refresh",
        "id": checkpoint_id,
        "derived_from": derived,
        "dry_run": dry_run,
        "diff": {
            "changed_sources": changed_sources,
            "missing_sources": missing_sources,
            "content_changed": proposed_content != (node.get("content") or ""),
            "before": node.get("content") or "",
            "after": proposed_content,
        },
        "contradictions": contradictions,
    }
    if dry_run:
        return preview
    if not yes:
        raise ValueError("checkpoint refresh requires --yes after reviewing --dry-run")
    if missing_sources:
        raise ValueError("checkpoint has missing source nodes; repair graph references before refresh")
    if contradictions:
        raise ValueError("checkpoint has unresolved contradictions; curate them before refresh")

    node["content"] = proposed_content
    node["updated_at"] = now_iso()
    ck_dir.mkdir(parents=True, exist_ok=True)
    refreshed_at = now_iso()
    snapshot = _snapshot_payload(
        graph,
        checkpoint_id=checkpoint_id,
        title=node.get("title") or checkpoint_id,
        node_ids=derived,
        timestamp_key="refreshed_at",
        timestamp=refreshed_at,
    )
    snap_path.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    preview["snapshot"] = str(snap_path)
    return preview
