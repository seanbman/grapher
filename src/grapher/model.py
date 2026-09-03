"""Normalize v1/v2 graph documents and node defaults."""

from __future__ import annotations

from typing import Any

from grapher.registry import (
    BUILTIN_NODE_TYPES,
    BUILTIN_RELS,
    CANONICAL_STAGE_ORDER,
    LIFECYCLE_STAGES,
    TRUTH_STATUSES,
    VERIFICATION_STATES,
    WORKFLOW_STATES,
    normalize_stage,
)

# Backward-compatible exports
NODE_TYPES = BUILTIN_NODE_TYPES
DEFAULT_RELS = BUILTIN_RELS

DEFAULT_NODE_STATUS = "unclassified"
DEFAULT_WORKFLOW_STATE = "not_applicable"
DEFAULT_VERIFICATION = "unverified"


def now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def slugify(text: str, *, max_len: int = 48) -> str:
    import re

    s = text.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")[:max_len].strip("-")
    return s or "node"


def make_id(title: str | None = None, explicit: str | None = None) -> str:
    import uuid

    if explicit:
        return explicit.strip()
    if title:
        base = slugify(title)
        return f"{base}-{uuid.uuid4().hex[:8]}"
    return uuid.uuid4().hex


def embed_text(node: dict[str, Any]) -> str:
    """Stable semantic text; operational metadata is deliberately excluded."""
    parts: list[str] = []
    title = (node.get("title") or "").strip()
    content = (node.get("content") or "").strip()
    tags = node.get("tags") or []
    if title:
        parts.append(title)
    if content:
        parts.append(content)
    if tags:
        parts.append(" ".join(str(t) for t in tags))
    return "\n".join(parts)


def empty_graph(
    *,
    name: str = "knowledge",
    domain: str = "general",
    kinds: list[str] | None = None,
    stages: list[str] | None = None,
    profile: str = "general",
) -> dict[str, Any]:
    ts = now_iso()
    return {
        "version": 2,
        "graph": {
            "name": name,
            "domain": domain,
            "kinds": kinds or ["knowledge"],
            "stages": stages or list(CANONICAL_STAGE_ORDER),
            "profile": profile,
            "created_at": ts,
            "updated_at": ts,
        },
        "nodes": {},
        "edges": [],
    }


def empty_vectors(
    *,
    model: str = "BAAI/bge-small-en-v1.5",
    provider: str = "fastembed",
    dims: int | None = None,
) -> dict[str, Any]:
    return {
        "version": 1,
        "model": model,
        "provider": provider,
        "dims": dims,
        "vectors": {},
    }


def normalize_stages(raw: Any) -> list[str] | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        return [normalize_stage(raw)]
    if isinstance(raw, list):
        out = [normalize_stage(str(s)) for s in raw if str(s).strip()]
        return out or None
    return None


def normalize_node(node: dict[str, Any], *, graph_meta: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return a shallow copy with v2 defaults applied (does not mutate input)."""
    out = dict(node)
    meta = dict(out.get("meta") or {})

    # Migrate legacy meta.status (ingest pending) vs truth status
    if "status" not in out and meta.get("status") in TRUTH_STATUSES:
        out["status"] = meta.pop("status")
    elif "status" not in out:
        out["status"] = DEFAULT_NODE_STATUS

    if "workflow_state" not in out:
        out["workflow_state"] = meta.pop("workflow_state", DEFAULT_WORKFLOW_STATE)

    if "verification" not in out:
        out["verification"] = meta.pop("verification", DEFAULT_VERIFICATION)

    if "stage" not in out:
        out["stage"] = normalize_stages(meta.pop("stage", None))

    for field in ("evidence", "source_refs", "owners"):
        if field not in out:
            out[field] = list(meta.pop(field, None) or [])

    for field in ("started_at", "completed_at", "due_at"):
        if field not in out and field in meta:
            out[field] = meta.pop(field)

    if "scope" not in out:
        out["scope"] = dict(meta.pop("scope", None) or {})
    if "provenance" not in out:
        out["provenance"] = dict(meta.pop("provenance", None) or {})
    if "finalized_at" not in out and "finalized_at" in meta:
        out["finalized_at"] = meta.pop("finalized_at")

    out["meta"] = meta
    return out


def normalize_graph(data: dict[str, Any]) -> dict[str, Any]:
    """Ensure graph metadata and node defaults; returns new dict."""
    out = dict(data)
    version = out.get("version", 1)
    if version >= 2:
        graph_meta = dict(out.get("graph") or {})
        graph_meta.setdefault("name", "knowledge")
        graph_meta.setdefault("domain", "general")
        graph_meta.setdefault("kinds", ["knowledge"])
        graph_meta.setdefault("stages", list(LIFECYCLE_STAGES))
        graph_meta.setdefault("profile", "general")
        out["graph"] = graph_meta
    nodes = out.get("nodes") or {}
    out["nodes"] = {
        nid: normalize_node(n, graph_meta=out.get("graph"))
        for nid, n in nodes.items()
    }
    out.setdefault("edges", [])
    return out


def graph_version(data: dict[str, Any]) -> int:
    return int(data.get("version", 1))


def make_node(
    *,
    id: str,
    type: str,
    title: str,
    content: str = "",
    path: str | None = None,
    tags: list[str] | None = None,
    meta: dict[str, Any] | None = None,
    existing: dict[str, Any] | None = None,
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
) -> dict[str, Any]:
    if not type or not type.strip():
        raise ValueError("node type must be non-empty")
    if status and status not in TRUTH_STATUSES:
        raise ValueError(f"unknown status {status!r}")
    if workflow_state and workflow_state not in WORKFLOW_STATES:
        raise ValueError(f"unknown workflow_state {workflow_state!r}")
    if verification and verification not in VERIFICATION_STATES:
        raise ValueError(f"unknown verification {verification!r}")

    ts = now_iso()
    merged_meta: dict[str, Any] = {}
    if existing:
        merged_meta.update(existing.get("meta") or {})
    if meta:
        merged_meta.update(meta)
    # LLM enrichment clears pending ingest stub flag in meta
    if content and content.strip():
        if merged_meta.get("source") == "ingest":
            merged_meta["enriched_at"] = ts
        if merged_meta.get("status") == "pending":
            merged_meta.pop("status", None)

    node: dict[str, Any] = {
        "id": id,
        "type": type,
        "title": title,
        "content": content,
        "path": path if path is not None else (existing or {}).get("path"),
        "tags": list(tags if tags is not None else (existing or {}).get("tags") or []),
        "meta": merged_meta,
        "created_at": (existing or {}).get("created_at", ts),
        "updated_at": ts,
    }

    for field, val, default in (
        ("stage", stage, (existing or {}).get("stage")),
        ("status", status, (existing or {}).get("status", DEFAULT_NODE_STATUS)),
        (
            "workflow_state",
            workflow_state,
            (existing or {}).get("workflow_state", DEFAULT_WORKFLOW_STATE),
        ),
        (
            "verification",
            verification,
            (existing or {}).get("verification", DEFAULT_VERIFICATION),
        ),
        ("evidence", evidence, (existing or {}).get("evidence")),
        ("source_refs", source_refs, (existing or {}).get("source_refs")),
        ("owners", owners, (existing or {}).get("owners")),
        ("scope", scope, (existing or {}).get("scope")),
        ("provenance", provenance, (existing or {}).get("provenance")),
        ("finalized_at", finalized_at, (existing or {}).get("finalized_at")),
    ):
        if val is not None:
            node[field] = val
        elif default is not None:
            node[field] = default
        elif field in ("evidence", "source_refs", "owners"):
            node[field] = []

    return normalize_node(node)


def make_edge(
    *,
    from_id: str,
    to_id: str,
    rel: str,
    note: str | None = None,
) -> dict[str, Any]:
    edge: dict[str, Any] = {
        "from": from_id,
        "to": to_id,
        "rel": rel,
        "created_at": now_iso(),
    }
    if note:
        edge["note"] = note
    return edge
