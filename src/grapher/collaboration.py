"""Local-first agent arms, immutable changesets, and deterministic reconciliation."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from grapher.audit import validate_graph
from grapher.config import load_config, save_config
from grapher.model import normalize_graph, now_iso
from grapher.store import load_graph, save_graph, vectors_path_for
from grapher.transport import graph_hash

ARMS_DIRNAME = "arms"
CHANGES_DIRNAME = "changes"
CONFLICTS_DIRNAME = "conflicts"
RECONCILE_STATE_FILENAME = "reconcile-state.json"


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _stable_hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-.")
    if not slug:
        raise ValueError("actor must contain at least one usable character")
    return slug


def grapher_root_for(graph_path: Path) -> Path:
    graph_path = graph_path.resolve()
    for candidate in [graph_path.parent, *graph_path.parents]:
        if candidate.name == ".grapher":
            return candidate
    return graph_path.parent


def collaboration_paths(graph_path: Path) -> dict[str, Path]:
    root = grapher_root_for(graph_path)
    shared = root / "shared"
    return {
        "root": root,
        "shared_graph": shared / "knowledge.json",
        "manifest": shared / "manifest.json",
        "changes": shared / CHANGES_DIRNAME,
        "arms": root / ARMS_DIRNAME,
        "conflicts": root / CONFLICTS_DIRNAME,
        "reconcile_state": root / RECONCILE_STATE_FILENAME,
        "canonical_graph": root / "knowledge.json",
    }


def create_arm(graph_path: Path, *, actor: str, force: bool = False) -> dict[str, Any]:
    paths = collaboration_paths(graph_path)
    base_path = paths["shared_graph"] if paths["shared_graph"].is_file() else graph_path
    if not base_path.is_file():
        raise FileNotFoundError("no shared or local graph exists; run grapher sync or grapher publish first")

    base = load_graph(base_path)
    actor_slug = _slug(actor)
    arm_path = paths["arms"] / actor_slug / "knowledge.json"
    if arm_path.exists() and not force:
        raise ValueError(f"arm already exists: {arm_path}; use --force to reset it")

    save_graph(arm_path, base)
    save_config(arm_path, load_config(paths["root"] / "knowledge.json"))
    _write_json(
        arm_path.parent / "arm-state.json",
        {
            "version": 1,
            "actor": actor,
            "base_graph_hash": graph_hash(base),
            "created_at": now_iso(),
        },
    )
    vpath = vectors_path_for(arm_path)
    if vpath.exists():
        vpath.unlink()
    return {
        "created": True,
        "actor": actor,
        "base_graph_hash": graph_hash(base),
        "graph": str(arm_path),
    }


def _edge_key(edge: dict[str, Any]) -> tuple[str, str, str]:
    return (str(edge.get("from") or ""), str(edge.get("to") or ""), str(edge.get("rel") or ""))


def _edge_semantic(edge: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in edge.items() if key != "created_at"}


def _node_patch(base: dict[str, Any], current: dict[str, Any]) -> list[dict[str, Any]]:
    fields = sorted((set(base) | set(current)) - {"updated_at"})
    patch: list[dict[str, Any]] = []
    for field in fields:
        before_present = field in base
        after_present = field in current
        before = base.get(field)
        after = current.get(field)
        if before_present == after_present and before == after:
            continue
        item: dict[str, Any] = {
            "field": field,
            "before_present": before_present,
            "after_present": after_present,
        }
        if before_present:
            item["before"] = before
        if after_present:
            item["after"] = after
        patch.append(item)
    return patch


def diff_graphs(base: dict[str, Any], current: dict[str, Any]) -> list[dict[str, Any]]:
    base = normalize_graph(base)
    current = normalize_graph(current)
    operations: list[dict[str, Any]] = []

    base_nodes = base.get("nodes") or {}
    current_nodes = current.get("nodes") or {}
    for node_id in sorted(set(base_nodes) | set(current_nodes)):
        before = base_nodes.get(node_id)
        after = current_nodes.get(node_id)
        if before is None:
            operations.append({"op": "add_node", "node": after})
        elif after is None:
            operations.append({"op": "remove_node", "node_id": node_id, "base": before})
        else:
            patch = _node_patch(before, after)
            if patch:
                operations.append(
                    {
                        "op": "update_node",
                        "node_id": node_id,
                        "changes": patch,
                        "updated_at": after.get("updated_at"),
                    }
                )

    base_edges = {_edge_key(edge): edge for edge in base.get("edges") or []}
    current_edges = {_edge_key(edge): edge for edge in current.get("edges") or []}
    for key in sorted(set(base_edges) | set(current_edges)):
        before = base_edges.get(key)
        after = current_edges.get(key)
        if before is None:
            operations.append({"op": "set_edge", "edge": after})
        elif after is None:
            operations.append({"op": "remove_edge", "key": list(key), "base": before})
        elif _edge_semantic(before) != _edge_semantic(after):
            operations.append({"op": "set_edge", "edge": after, "base": before})
    return operations


def create_changeset(graph_path: Path, *, actor: str) -> dict[str, Any]:
    paths = collaboration_paths(graph_path)
    if not paths["shared_graph"].is_file():
        raise FileNotFoundError("shared graph not found; run grapher publish or pull/sync first")
    if not graph_path.is_file():
        raise FileNotFoundError(f"working graph not found: {graph_path}")

    base = load_graph(paths["shared_graph"])
    current = load_graph(graph_path)
    validation = validate_graph(current, graph_path)
    if not validation["valid"]:
        raise ValueError(f"cannot create changeset from invalid graph ({validation['error_count']} error(s))")

    operations = diff_graphs(base, current)
    if not operations:
        return {"created": False, "reason": "unchanged", "base_graph_hash": graph_hash(base)}

    identity = {
        "version": 1,
        "base_graph_hash": graph_hash(base),
        "actor": actor,
        "operations": operations,
    }
    changeset_id = _stable_hash(identity)[:16]
    record = {
        **identity,
        "changeset_id": changeset_id,
        "created_at": now_iso(),
    }
    target = paths["changes"] / _slug(actor) / f"{changeset_id}.json"
    if not target.exists():
        _write_json(target, record)
    return {
        "created": True,
        "changeset_id": changeset_id,
        "base_graph_hash": identity["base_graph_hash"],
        "operations": len(operations),
        "path": str(target),
    }


def _load_changesets(changes_dir: Path) -> list[dict[str, Any]]:
    if not changes_dir.is_dir():
        return []
    records: list[dict[str, Any]] = []
    for path in sorted(changes_dir.rglob("*.json")):
        record = _read_json(path)
        if not record.get("changeset_id") or not isinstance(record.get("operations"), list):
            raise ValueError(f"invalid changeset: {path}")
        record["_path"] = str(path)
        records.append(record)
    return records


def _same_value(items: list[Any]) -> bool:
    return all(item == items[0] for item in items[1:])


def reconcile_graph(graph_path: Path) -> dict[str, Any]:
    paths = collaboration_paths(graph_path)
    if not paths["shared_graph"].is_file():
        raise FileNotFoundError("shared graph not found; run grapher publish or pull/sync first")

    base = load_graph(paths["shared_graph"])
    base_hash = graph_hash(base)
    manifest = _read_json(paths["manifest"]) if paths["manifest"].is_file() else {}
    included = set(manifest.get("included_changesets") or [])
    changesets = [c for c in _load_changesets(paths["changes"]) if c["changeset_id"] not in included]

    conflicts: list[dict[str, Any]] = []
    eligible: list[dict[str, Any]] = []
    for changeset in changesets:
        if changeset.get("base_graph_hash") != base_hash:
            conflicts.append(
                {
                    "type": "stale_base",
                    "changeset_id": changeset["changeset_id"],
                    "actor": changeset.get("actor"),
                    "expected_base": base_hash,
                    "actual_base": changeset.get("base_graph_hash"),
                }
            )
        else:
            eligible.append(changeset)

    node_ops: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = {}
    edge_ops: dict[tuple[str, str, str], list[tuple[dict[str, Any], dict[str, Any]]]] = {}
    for changeset in eligible:
        for op in changeset["operations"]:
            kind = op.get("op")
            if kind == "add_node":
                node_id = str((op.get("node") or {}).get("id") or "")
                node_ops.setdefault(node_id, []).append((changeset, op))
            elif kind in {"update_node", "remove_node"}:
                node_ops.setdefault(str(op.get("node_id") or ""), []).append((changeset, op))
            elif kind == "set_edge":
                edge_ops.setdefault(_edge_key(op.get("edge") or {}), []).append((changeset, op))
            elif kind == "remove_edge":
                key = tuple(str(x) for x in (op.get("key") or []))
                if len(key) == 3:
                    edge_ops.setdefault(key, []).append((changeset, op))
                else:
                    conflicts.append({"type": "invalid_operation", "changeset_id": changeset["changeset_id"]})
            else:
                conflicts.append({"type": "invalid_operation", "changeset_id": changeset["changeset_id"], "op": kind})

    result = copy.deepcopy(normalize_graph(base))
    base_nodes = result.get("nodes") or {}
    for node_id, entries in sorted(node_ops.items()):
        kinds = {op["op"] for _, op in entries}
        if "add_node" in kinds:
            nodes = [op["node"] for _, op in entries if op["op"] == "add_node"]
            if node_id in base_nodes or kinds != {"add_node"} or not _same_value(nodes):
                conflicts.append({"type": "node_conflict", "node_id": node_id, "changesets": [c["changeset_id"] for c, _ in entries]})
            else:
                base_nodes[node_id] = copy.deepcopy(nodes[0])
            continue

        if "remove_node" in kinds:
            if kinds != {"remove_node"}:
                conflicts.append({"type": "node_conflict", "node_id": node_id, "changesets": [c["changeset_id"] for c, _ in entries]})
            else:
                base_nodes.pop(node_id, None)
            continue

        if node_id not in base_nodes:
            conflicts.append({"type": "node_missing", "node_id": node_id, "changesets": [c["changeset_id"] for c, _ in entries]})
            continue

        field_values: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = {}
        updated_times: list[str] = []
        for changeset, op in entries:
            if op.get("updated_at"):
                updated_times.append(str(op["updated_at"]))
            for change in op.get("changes") or []:
                field_values.setdefault(str(change.get("field")), []).append((changeset, change))

        for field, changes in sorted(field_values.items()):
            signatures = [
                (bool(change.get("after_present")), change.get("after"))
                for _, change in changes
            ]
            if not _same_value(signatures):
                conflicts.append(
                    {
                        "type": "field_conflict",
                        "node_id": node_id,
                        "field": field,
                        "changesets": [c["changeset_id"] for c, _ in changes],
                    }
                )
                continue
            after_present, after = signatures[0]
            if after_present:
                base_nodes[node_id][field] = copy.deepcopy(after)
            else:
                base_nodes[node_id].pop(field, None)
        if updated_times:
            base_nodes[node_id]["updated_at"] = max(updated_times)

    edges = {_edge_key(edge): copy.deepcopy(edge) for edge in result.get("edges") or []}
    for key, entries in sorted(edge_ops.items()):
        kinds = {op["op"] for _, op in entries}
        if "remove_edge" in kinds and "set_edge" in kinds:
            conflicts.append({"type": "edge_conflict", "edge": list(key), "changesets": [c["changeset_id"] for c, _ in entries]})
            continue
        if kinds == {"remove_edge"}:
            edges.pop(key, None)
            continue
        candidates = [op["edge"] for _, op in entries]
        semantic = [_edge_semantic(edge) for edge in candidates]
        if not _same_value(semantic):
            conflicts.append({"type": "edge_conflict", "edge": list(key), "changesets": [c["changeset_id"] for c, _ in entries]})
            continue
        chosen = copy.deepcopy(candidates[0])
        timestamps = [str(edge.get("created_at")) for edge in candidates if edge.get("created_at")]
        if timestamps:
            chosen["created_at"] = min(timestamps)
        edges[key] = chosen

    if conflicts:
        conflict_id = _stable_hash({"base": base_hash, "conflicts": conflicts})[:16]
        report_path = paths["conflicts"] / f"{conflict_id}.json"
        _write_json(report_path, {"version": 1, "conflict_id": conflict_id, "base_graph_hash": base_hash, "conflicts": conflicts})
        return {"reconciled": False, "conflicts": len(conflicts), "conflict_report": str(report_path)}

    result["nodes"] = base_nodes
    result["edges"] = [edges[key] for key in sorted(edges)]
    target = paths["canonical_graph"]
    validation = validate_graph(result, target)
    if not validation["valid"]:
        raise ValueError(f"reconciled graph failed validation ({validation['error_count']} error(s))")

    save_graph(target, result)
    result_hash = graph_hash(result)
    applied = sorted(c["changeset_id"] for c in eligible)
    _write_json(
        paths["reconcile_state"],
        {
            "version": 1,
            "base_graph_hash": base_hash,
            "result_graph_hash": result_hash,
            "applied_changesets": applied,
            "reconciled_at": now_iso(),
        },
    )
    vpath = vectors_path_for(target)
    if vpath.exists():
        vpath.unlink()
    return {
        "reconciled": True,
        "base_graph_hash": base_hash,
        "result_graph_hash": result_hash,
        "changesets": len(applied),
        "graph": str(target),
    }
