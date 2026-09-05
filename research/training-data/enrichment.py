#!/usr/bin/env python3
"""Review-first, non-mutating legacy semantic enrichment workflow."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WORKFLOW_VERSION = "0.1.0"
ROOT = Path(__file__).resolve().parents[2]


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


legacy = _load_module("legacy_normalization", Path(__file__).with_name("legacy_normalization.py"))
semantic = _load_module("grapher_semantic", ROOT / "src" / "grapher" / "semantic.py")


def load(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def stable_id(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()[:16]


def _source_view(node_id: str, node: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": node_id,
        "type": str(node.get("type") or "unknown"),
        "title": str(node.get("title") or node_id),
        "content": str(node.get("content") or ""),
        "path": node.get("path"),
        "stage": node.get("stage"),
        "status": node.get("status"),
        "verification": node.get("verification"),
    }


def review_item(node_id: str, node: dict[str, Any]) -> dict[str, Any]:
    classification = legacy.classify(node)
    candidates = []
    for node_type in classification["candidate_types"]:
        contract = semantic.semantic_contract(node_type)
        candidates.append(
            {
                "type": node_type,
                "required_fields": contract["required_fields"],
                "field_types": contract["field_types"],
                "constraints": contract["constraints"],
                "values": {},
            }
        )
    return {
        "source": _source_view(node_id, node),
        "disposition": classification["disposition"],
        "reason": classification["reason"],
        "candidates": candidates,
        "rule": "Candidate fields are intentionally empty; semantic meaning must be supplied explicitly.",
    }


def preview(graph: dict[str, Any], ids: list[str] | None = None) -> dict[str, Any]:
    original = deepcopy(graph)
    nodes = graph.get("nodes") or {}
    selected = sorted(ids) if ids else sorted(nodes)
    records = []
    missing = []
    for node_id in selected:
        node = nodes.get(node_id)
        if node is None:
            missing.append(node_id)
            continue
        item = review_item(node_id, node)
        if item["disposition"] == "enrichment_required":
            records.append(item)
    if graph != original:
        raise RuntimeError("enrichment preview mutated source graph")
    return {
        "workflow_version": WORKFLOW_VERSION,
        "review_count": len(records),
        "missing_ids": missing,
        "records": records,
    }


def compose_successor(
    graph: dict[str, Any],
    node_id: str,
    node_type: str,
    values: dict[str, Any],
    *,
    actor_id: str,
    actor_kind: str,
    reason: str,
    successor_id: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    original = deepcopy(graph)
    nodes = graph.get("nodes") or {}
    source = nodes.get(node_id)
    if source is None:
        raise ValueError(f"unknown legacy node {node_id!r}")
    classification = legacy.classify(source)
    if classification["disposition"] != "enrichment_required":
        raise ValueError(f"node {node_id!r} is not enrichment_required")
    if node_type not in classification["candidate_types"]:
        raise ValueError(
            f"semantic type {node_type!r} is not an allowed candidate for {node_id!r}: "
            + ", ".join(classification["candidate_types"])
        )
    if not actor_id.strip() or not actor_kind.strip() or not reason.strip():
        raise ValueError("actor_id, actor_kind, and reason are required")

    payload = semantic.parse_semantic_content(node_type, json.dumps(values))
    created_at = created_at or datetime.now(timezone.utc).isoformat()
    successor_id = successor_id or f"{node_type}-enriched-{stable_id(node_id, node_type, json.dumps(payload, sort_keys=True))}"
    if successor_id in nodes:
        raise ValueError(f"successor id {successor_id!r} already exists")

    successor = {
        "id": successor_id,
        "type": node_type,
        "title": str(source.get("title") or node_id),
        "content": json.dumps(payload, sort_keys=True, separators=(",", ":")),
        "semantic": payload,
        "status": "proposed",
        "workflow_state": "not_applicable",
        "verification": "unverified",
        "evidence": [],
        "source_refs": list(source.get("source_refs") or []),
        "owners": list(source.get("owners") or []),
        "scope": dict(source.get("scope") or {}),
        "stage": source.get("stage"),
        "provenance": {
            "actor_id": actor_id,
            "actor_kind": actor_kind,
            "actor_role": "semantic-enricher",
            "source": "research_enrichment",
            "integrity": "declared",
            "recorded_at": created_at,
        },
    }
    relation = {
        "from": successor_id,
        "to": node_id,
        "rel": "derived_from",
        "created_at": created_at,
        "note": "Explicit semantic enrichment of preserved legacy record.",
    }
    bundle = {
        "workflow_version": WORKFLOW_VERSION,
        "source": _source_view(node_id, source),
        "successor": successor,
        "relation": relation,
        "review": {
            "candidate_type": node_type,
            "supplied_fields": sorted(payload),
            "reason": reason,
            "validated": True,
            "source_mutated": False,
        },
    }
    if graph != original:
        raise RuntimeError("successor composition mutated source graph")
    return bundle


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    p_preview = sub.add_parser("preview")
    p_preview.add_argument("--graph", required=True)
    p_preview.add_argument("--id", action="append", dest="ids")
    p_preview.add_argument("--out")

    p_compose = sub.add_parser("compose")
    p_compose.add_argument("--graph", required=True)
    p_compose.add_argument("--node-id", required=True)
    p_compose.add_argument("--type", required=True, dest="node_type")
    p_compose.add_argument("--values", required=True)
    p_compose.add_argument("--actor-id", required=True)
    p_compose.add_argument("--actor-kind", required=True)
    p_compose.add_argument("--reason", required=True)
    p_compose.add_argument("--successor-id")
    p_compose.add_argument("--out")

    args = parser.parse_args()
    graph = load(args.graph)
    if args.command == "preview":
        result = preview(graph, args.ids)
    else:
        result = compose_successor(
            graph,
            args.node_id,
            args.node_type,
            load(args.values),
            actor_id=args.actor_id,
            actor_kind=args.actor_kind,
            reason=args.reason,
            successor_id=args.successor_id,
        )
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
