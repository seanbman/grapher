#!/usr/bin/env python3
"""Conservative, read-only preview of how legacy Grapher nodes could enter typed semantics."""

from __future__ import annotations

import argparse, hashlib, json
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any

PREVIEW_VERSION = "0.1.0"
SEMANTIC_TYPES = {"observation","problem","question","hypothesis","requirement","constraint","proposal","decision","task","implementation","test","result","failure","lesson"}
LEGACY_ENRICHMENT = {
    "finding": ["observation", "problem", "result", "failure", "lesson"],
    "instruction": ["requirement", "constraint"],
}
CONTEXT_ONLY_TYPES = {"concept", "document", "image", "video", "checkpoint"}


def load(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def classify(node: dict[str, Any]) -> dict[str, Any]:
    node_type = str(node.get("type") or "unknown")
    semantic = node.get("semantic")
    if node_type in SEMANTIC_TYPES and isinstance(semantic, dict) and semantic:
        return {"disposition":"mechanically_mappable","candidate_types":[node_type],"reason":"already_has_canonical_semantic_payload"}
    if node_type in SEMANTIC_TYPES:
        return {"disposition":"enrichment_required","candidate_types":[node_type],"reason":"typed_free_text_missing_required_semantic_payload"}
    if node_type in LEGACY_ENRICHMENT:
        return {"disposition":"enrichment_required","candidate_types":LEGACY_ENRICHMENT[node_type],"reason":"legacy_type_is_semantically_ambiguous"}
    if node_type in CONTEXT_ONLY_TYPES:
        return {"disposition":"context_only","candidate_types":[],"reason":"artifact_or_context_record_has_no_safe_semantic_retype"}
    return {"disposition":"context_only","candidate_types":[],"reason":"unknown_legacy_type_has_no_safe_mapping"}


def preview(graph: dict[str, Any], source_ref: str | None = None) -> dict[str, Any]:
    original = deepcopy(graph)
    nodes = graph.get("nodes") or {}
    rows = []
    dispositions = Counter(); types = Counter(); candidate_types = Counter(); reasons = Counter()
    for node_id in sorted(nodes):
        node = nodes[node_id]
        result = classify(node)
        row = {"id":str(node_id),"type":str(node.get("type") or "unknown"),**result}
        rows.append(row)
        dispositions[row["disposition"]] += 1
        types[row["type"]] += 1
        reasons[row["reason"]] += 1
        candidate_types.update(row["candidate_types"])
    if graph != original:
        raise RuntimeError("preview mutated source graph")
    digest = hashlib.sha256(json.dumps(graph,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    metrics = {
        "preview_version":PREVIEW_VERSION,
        "source_ref":source_ref,
        "graph_hash":digest,
        "node_count":len(nodes),
        "disposition_counts":dict(sorted(dispositions.items())),
        "node_type_counts":dict(sorted(types.items())),
        "candidate_semantic_type_counts":dict(sorted(candidate_types.items())),
        "reason_counts":dict(sorted(reasons.items())),
    }
    return {"metrics":metrics,"records":rows}


def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument("--graph",required=True)
    p.add_argument("--source-ref")
    p.add_argument("--out")
    p.add_argument("--metrics")
    a=p.parse_args()
    result=preview(load(a.graph),a.source_ref)
    if a.out: Path(a.out).write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    if a.metrics: Path(a.metrics).write_text(json.dumps(result["metrics"],indent=2,sort_keys=True)+"\n")
    if not (a.out or a.metrics): print(json.dumps(result["metrics"],indent=2,sort_keys=True))
    return 0

if __name__ == "__main__": raise SystemExit(main())
