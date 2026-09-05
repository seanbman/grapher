"""Git transport boundary for shared Grapher knowledge."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from grapher.audit import validate_graph
from grapher.embed import DEFAULT_MODEL, EmbedError
from grapher.model import normalize_graph, now_iso
from grapher.store import load_graph, load_vectors, save_graph, vectors_path_for

SHARED_DIRNAME = "shared"
SHARED_GRAPH_FILENAME = "knowledge.json"
MANIFEST_FILENAME = "manifest.json"
HISTORY_DIRNAME = "history"
SYNC_STATE_FILENAME = "sync-state.json"
RECONCILE_STATE_FILENAME = "reconcile-state.json"


def _canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def graph_hash(graph: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_bytes(normalize_graph(graph))).hexdigest()


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


def shared_paths(graph_path: Path) -> dict[str, Path]:
    shared = graph_path.parent / SHARED_DIRNAME
    return {
        "shared": shared,
        "graph": shared / SHARED_GRAPH_FILENAME,
        "manifest": shared / MANIFEST_FILENAME,
        "history": shared / HISTORY_DIRNAME,
        "sync_state": graph_path.parent / SYNC_STATE_FILENAME,
        "reconcile_state": graph_path.parent / RECONCILE_STATE_FILENAME,
    }


def _included_changesets(
    current_hash: str,
    previous_manifest: dict[str, Any],
    reconcile_state_path: Path,
) -> tuple[list[str], list[str]]:
    included = set(previous_manifest.get("included_changesets") or [])
    applied: list[str] = []
    if reconcile_state_path.is_file():
        state = _read_json(reconcile_state_path)
        if state.get("result_graph_hash") == current_hash:
            applied = sorted(set(state.get("applied_changesets") or []))
            included.update(applied)
    return sorted(included), applied


def publish_graph(graph_path: Path) -> dict[str, Any]:
    graph = load_graph(graph_path)
    validation = validate_graph(graph, graph_path)
    if not validation["valid"]:
        raise ValueError(
            f"cannot publish invalid graph ({validation['error_count']} validation error(s))"
        )

    paths = shared_paths(graph_path)
    current_hash = graph_hash(graph)
    previous_manifest = _read_json(paths["manifest"]) if paths["manifest"].is_file() else {}
    previous_hash = previous_manifest.get("graph_hash")
    included_changesets, applied_changesets = _included_changesets(
        current_hash,
        previous_manifest,
        paths["reconcile_state"],
    )
    previous_included = sorted(previous_manifest.get("included_changesets") or [])

    if paths["graph"].is_file() and previous_hash == current_hash:
        if included_changesets != previous_included:
            manifest = dict(previous_manifest)
            manifest["included_changesets"] = included_changesets
            _write_json(paths["manifest"], manifest)
            _write_json(paths["sync_state"], {"last_synced_hash": current_hash})
            return {
                "published": False,
                "reason": "metadata_updated",
                "graph_hash": current_hash,
                "included_changesets": len(included_changesets),
                "shared_graph": str(paths["graph"]),
            }
        _write_json(paths["sync_state"], {"last_synced_hash": current_hash})
        return {
            "published": False,
            "reason": "unchanged",
            "graph_hash": current_hash,
            "shared_graph": str(paths["graph"]),
        }

    ts = now_iso()
    publication_id = current_hash[:16]
    vectors = load_vectors(vectors_path_for(graph_path))
    embedding = {
        "provider": vectors.get("provider") or "fastembed",
        "model": vectors.get("model") or DEFAULT_MODEL,
        "dims": vectors.get("dims"),
    }

    _write_json(paths["graph"], normalize_graph(graph))
    record = {
        "version": 1,
        "publication_id": publication_id,
        "published_at": ts,
        "graph_hash": current_hash,
        "previous_graph_hash": previous_hash,
        "nodes": len(graph.get("nodes") or {}),
        "edges": len(graph.get("edges") or []),
        "embedding": embedding,
        "changesets": applied_changesets,
    }
    history_path = paths["history"] / f"{publication_id}.json"
    if not history_path.exists():
        _write_json(history_path, record)

    manifest = {
        "version": 1,
        "schema_version": graph.get("version", 1),
        "publication_id": publication_id,
        "published_at": ts,
        "graph_hash": current_hash,
        "embedding": embedding,
        "included_changesets": included_changesets,
    }
    _write_json(paths["manifest"], manifest)
    _write_json(paths["sync_state"], {"last_synced_hash": current_hash})
    return {
        "published": True,
        "publication_id": publication_id,
        "graph_hash": current_hash,
        "included_changesets": len(included_changesets),
        "shared_graph": str(paths["graph"]),
        "history_record": str(history_path),
        "manifest": str(paths["manifest"]),
    }


def sync_graph(
    graph_path: Path,
    *,
    force: bool = False,
    rebuild_vectors: bool = True,
) -> dict[str, Any]:
    paths = shared_paths(graph_path)
    if not paths["graph"].is_file():
        raise FileNotFoundError(
            f"shared graph not found: {paths['graph']}; pull Git changes or run grapher publish"
        )

    shared_graph = normalize_graph(_read_json(paths["graph"]))
    shared_hash = graph_hash(shared_graph)
    manifest = _read_json(paths["manifest"]) if paths["manifest"].is_file() else {}
    declared_hash = manifest.get("graph_hash")
    if declared_hash and declared_hash != shared_hash:
        raise ValueError("shared manifest graph_hash does not match shared knowledge.json")

    state = _read_json(paths["sync_state"]) if paths["sync_state"].is_file() else {}
    last_synced_hash = state.get("last_synced_hash")
    local_hash = None
    if graph_path.is_file():
        local_hash = graph_hash(load_graph(graph_path))
        clean_hashes = {shared_hash}
        if last_synced_hash:
            clean_hashes.add(last_synced_hash)
        if local_hash not in clean_hashes and not force:
            raise ValueError(
                "local graph contains unpublished changes; publish them first or use grapher sync --force"
            )

    save_graph(graph_path, shared_graph)
    _write_json(paths["sync_state"], {"last_synced_hash": shared_hash})

    vpath = vectors_path_for(graph_path)
    if vpath.exists():
        vpath.unlink()

    vector_result: dict[str, Any]
    if rebuild_vectors:
        from grapher import search as search_module

        try:
            vector_result = {"status": "rebuilt", **search_module.reindex(shared_graph, graph_path)}
        except EmbedError as exc:
            vector_result = {"status": "pending", "reason": str(exc)}
    else:
        vector_result = {"status": "skipped"}

    return {
        "synced": True,
        "graph_hash": shared_hash,
        "previous_local_hash": local_hash,
        "graph": str(graph_path),
        "vectors": vector_result,
    }
