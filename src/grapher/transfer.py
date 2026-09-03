"""Portable graph pack / unpack for transplanting ideas between projects."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from grapher.model import empty_graph, empty_vectors, now_iso
from grapher.store import (
    init_store,
    load_graph,
    load_vectors,
    save_graph_mutation,
    save_vectors,
    vectors_path_for,
)

PACK_FORMAT = "grapher-pack"
PACK_VERSION = 1


class TransferError(Exception):
    pass


def build_pack(
    graph: dict[str, Any],
    vectors: dict[str, Any] | None,
    *,
    name: str = "",
    description: str = "",
    source_graph: str = "",
    include_vectors: bool = True,
) -> dict[str, Any]:
    pack_vectors = None
    if include_vectors and vectors and (vectors.get("vectors") or {}):
        pack_vectors = copy.deepcopy(vectors)
    return {
        "format": PACK_FORMAT,
        "version": PACK_VERSION,
        "meta": {
            "name": name or "untitled",
            "description": description or "",
            "exported_at": now_iso(),
            "source_graph": source_graph,
        },
        "graph": {
            "version": graph.get("version", 1),
            "nodes": copy.deepcopy(graph.get("nodes") or {}),
            "edges": copy.deepcopy(graph.get("edges") or []),
        },
        "vectors": pack_vectors,
    }


def write_pack(path: Path, pack: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(pack, indent=2, ensure_ascii=False) + "\n"
    path.write_text(text, encoding="utf-8")


def read_pack(path: Path) -> dict[str, Any]:
    path = Path(path)
    if not path.is_file():
        raise TransferError(f"pack not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise TransferError(f"invalid pack JSON: {e}") from e
    if not isinstance(data, dict):
        raise TransferError("pack must be a JSON object")
    if data.get("format") != PACK_FORMAT:
        raise TransferError(
            f"unknown pack format {data.get('format')!r}; expected {PACK_FORMAT!r}"
        )
    if int(data.get("version") or 0) != PACK_VERSION:
        raise TransferError(
            f"unsupported pack version {data.get('version')!r}; expected {PACK_VERSION}"
        )
    graph = data.get("graph")
    if not isinstance(graph, dict) or "nodes" not in graph or "edges" not in graph:
        raise TransferError("pack missing graph.nodes / graph.edges")
    data.setdefault("meta", {})
    if "vectors" not in data:
        data["vectors"] = None
    return data


def _apply_prefix(graph: dict[str, Any], prefix: str) -> dict[str, Any]:
    if not prefix:
        return copy.deepcopy(graph)
    nodes_in = graph.get("nodes") or {}
    nodes_out: dict[str, Any] = {}
    for nid, node in nodes_in.items():
        new_id = f"{prefix}{nid}"
        n = copy.deepcopy(node)
        n["id"] = new_id
        nodes_out[new_id] = n
    edges_out = []
    for e in graph.get("edges") or []:
        ne = copy.deepcopy(e)
        if ne.get("from"):
            ne["from"] = f"{prefix}{ne['from']}"
        if ne.get("to"):
            ne["to"] = f"{prefix}{ne['to']}"
        edges_out.append(ne)
    return {"version": graph.get("version", 1), "nodes": nodes_out, "edges": edges_out}


def _prefix_vectors(
    vectors: dict[str, Any] | None, prefix: str
) -> dict[str, Any] | None:
    if not vectors or not prefix:
        return copy.deepcopy(vectors) if vectors else None
    out = copy.deepcopy(vectors)
    raw = out.get("vectors") or {}
    out["vectors"] = {f"{prefix}{nid}": vec for nid, vec in raw.items()}
    return out


def merge_graph(
    local: dict[str, Any],
    incoming: dict[str, Any],
    *,
    prefix: str = "",
) -> dict[str, Any]:
    """Merge incoming into local. Incoming nodes win on id conflict."""
    src = _apply_prefix(incoming, prefix)
    local = copy.deepcopy(local)
    local.setdefault("nodes", {})
    local.setdefault("edges", [])

    nodes_added = 0
    nodes_updated = 0
    for nid, node in (src.get("nodes") or {}).items():
        if nid in local["nodes"]:
            nodes_updated += 1
        else:
            nodes_added += 1
        local["nodes"][nid] = copy.deepcopy(node)

    existing = {
        (e.get("from"), e.get("to"), e.get("rel")) for e in local["edges"]
    }
    edges_added = 0
    for e in src.get("edges") or []:
        key = (e.get("from"), e.get("to"), e.get("rel"))
        if key in existing:
            continue
        local["edges"].append(copy.deepcopy(e))
        existing.add(key)
        edges_added += 1

    return {
        "graph": local,
        "nodes_added": nodes_added,
        "nodes_updated": nodes_updated,
        "edges_added": edges_added,
        "nodes_total": len(local["nodes"]),
        "edges_total": len(local["edges"]),
    }


def merge_vectors(
    local: dict[str, Any],
    incoming: dict[str, Any] | None,
    *,
    prefix: str = "",
    imported_ids: set[str] | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    """
    Merge pack vectors into local when models match.
    Returns (vectors_or_None, hint_or_None).
    """
    if not incoming or not (incoming.get("vectors") or {}):
        return local if (local.get("vectors") or {}) else None, None

    incoming = _prefix_vectors(incoming, prefix) or incoming
    local = copy.deepcopy(local) if local else empty_vectors()

    in_model = incoming.get("model")
    loc_model = local.get("model")
    loc_has = bool(local.get("vectors"))

    if loc_has and loc_model and in_model and loc_model != in_model:
        return local, (
            f"vector model mismatch (local={loc_model}, pack={in_model}); "
            "kept local vectors; run grapher reindex for imported nodes"
        )

    # adopt pack model metadata if local empty
    if not loc_has:
        local["model"] = incoming.get("model")
        local["provider"] = incoming.get("provider")
        local["dims"] = incoming.get("dims")
        local["version"] = incoming.get("version", 1)
        local["vectors"] = {}

    if loc_has and in_model and not loc_model:
        local["model"] = in_model
        local["provider"] = incoming.get("provider")
        local["dims"] = incoming.get("dims")

    # if still mismatched somehow after empty local adopt — already handled
    if local.get("model") and in_model and local["model"] != in_model:
        return local, (
            f"vector model mismatch (local={local.get('model')}, pack={in_model}); "
            "skipped pack vectors; run grapher reindex"
        )

    vecs = dict(local.get("vectors") or {})
    for nid, vec in (incoming.get("vectors") or {}).items():
        if imported_ids is not None and nid not in imported_ids:
            continue
        vecs[nid] = vec
    local["vectors"] = vecs
    return local, None


def pack_graph(
    graph_path: Path,
    out_path: Path,
    *,
    name: str = "",
    description: str = "",
    include_vectors: bool = True,
) -> dict[str, Any]:
    graph = load_graph(graph_path)
    vpath = vectors_path_for(graph_path)
    vectors = load_vectors(vpath) if vpath.is_file() else None
    pack = build_pack(
        graph,
        vectors,
        name=name,
        description=description,
        source_graph=str(graph_path),
        include_vectors=include_vectors,
    )
    write_pack(out_path, pack)
    return {
        "action": "pack",
        "path": str(out_path.resolve()),
        "name": pack["meta"]["name"],
        "description": pack["meta"].get("description") or "",
        "nodes": len(pack["graph"]["nodes"]),
        "edges": len(pack["graph"]["edges"]),
        "vectors": len((pack.get("vectors") or {}).get("vectors") or {}),
        "exported_at": pack["meta"]["exported_at"],
    }


def unpack_graph(
    graph_path: Path,
    pack_path: Path,
    *,
    mode: str = "merge",
    prefix: str = "",
    include_vectors: bool = True,
) -> dict[str, Any]:
    pack = read_pack(pack_path)
    mode = mode.lower()
    if mode not in {"merge", "replace"}:
        raise TransferError(f"unknown unpack mode: {mode}")

    init_store(graph_path)
    before = load_graph(graph_path, normalize=False)
    incoming = pack["graph"]
    pack_vectors = pack.get("vectors") if include_vectors else None
    hint = None

    if mode == "replace":
        graph = _apply_prefix(incoming, prefix)
        save_graph_mutation(graph_path, graph, action="graph_replaced", before=before,
                            source="unpack", context={"pack": str(pack_path), "prefix": prefix})
        vpath = vectors_path_for(graph_path)
        if pack_vectors:
            vectors = _prefix_vectors(pack_vectors, prefix) or pack_vectors
            save_vectors(vpath, vectors)
            vectors_count = len(vectors.get("vectors") or {})
        else:
            save_vectors(vpath, empty_vectors())
            vectors_count = 0
            if include_vectors and not pack.get("vectors"):
                hint = "pack had no vectors; run grapher reindex"
            elif not include_vectors:
                hint = "vectors skipped; run grapher reindex"
        return {
            "action": "unpack",
            "mode": "replace",
            "pack": str(Path(pack_path).resolve()),
            "graph": str(graph_path),
            "name": (pack.get("meta") or {}).get("name"),
            "prefix": prefix or None,
            "nodes": len(graph["nodes"]),
            "edges": len(graph["edges"]),
            "nodes_added": len(graph["nodes"]),
            "nodes_updated": 0,
            "edges_added": len(graph["edges"]),
            "vectors": vectors_count,
            "hint": hint,
        }

    # merge
    local = load_graph(graph_path)
    merged = merge_graph(local, incoming, prefix=prefix)
    save_graph_mutation(graph_path, merged["graph"], action="graph_merged", before=before,
                        source="unpack", context={"pack": str(pack_path), "prefix": prefix})

    imported_ids = {
        (f"{prefix}{nid}" if prefix else nid)
        for nid in (incoming.get("nodes") or {})
    }
    vpath = vectors_path_for(graph_path)
    local_vecs = load_vectors(vpath) if vpath.is_file() else empty_vectors()
    vectors_count = 0
    if pack_vectors:
        new_vecs, hint = merge_vectors(
            local_vecs,
            pack_vectors,
            prefix=prefix,
            imported_ids=imported_ids,
        )
        if new_vecs is not None:
            save_vectors(vpath, new_vecs)
            vectors_count = len(
                [
                    nid
                    for nid in (new_vecs.get("vectors") or {})
                    if nid in imported_ids
                ]
            )
    else:
        if include_vectors and not pack.get("vectors"):
            hint = "pack had no vectors; run grapher reindex for imported nodes"
        elif not include_vectors:
            hint = "vectors skipped; run grapher reindex for imported nodes"

    return {
        "action": "unpack",
        "mode": "merge",
        "pack": str(Path(pack_path).resolve()),
        "graph": str(graph_path),
        "name": (pack.get("meta") or {}).get("name"),
        "prefix": prefix or None,
        "nodes_added": merged["nodes_added"],
        "nodes_updated": merged["nodes_updated"],
        "edges_added": merged["edges_added"],
        "nodes": merged["nodes_total"],
        "edges": merged["edges_total"],
        "vectors": vectors_count,
        "hint": hint,
    }
