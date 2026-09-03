"""Non-mutating structural validation and semantic graph health audit."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from grapher.config import allowed_node_types, allowed_relations, load_config
from grapher.model import graph_version, normalize_graph
from grapher.query import node_stages, superseded_by, supersedes_targets
from grapher.registry import (
    EVIDENCE_TYPES,
    LIFECYCLE_STAGES,
    PROVENANCE_INTEGRITIES,
    TRUTH_STATUSES,
    VERIFICATION_STATES,
    WORKFLOW_STATES,
)


class ValidationIssue:
    def __init__(self, level: str, code: str, message: str, **context: Any):
        self.level, self.code, self.message, self.context = level, code, message, context

    def to_dict(self) -> dict[str, Any]:
        return {"level": self.level, "code": self.code, "message": self.message, **self.context}


def _timestamp_ok(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def _relation_cycles(graph: dict[str, Any], relations: set[str]) -> list[list[str]]:
    adjacency: dict[str, list[str]] = defaultdict(list)
    for edge in graph.get("edges") or []:
        if edge.get("rel") in relations:
            adjacency[str(edge.get("from"))].append(str(edge.get("to")))
    cycles: list[list[str]] = []
    visiting: list[str] = []
    done: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            cycle = visiting[visiting.index(node):] + [node]
            if cycle not in cycles:
                cycles.append(cycle)
            return
        if node in done:
            return
        visiting.append(node)
        for target in adjacency.get(node, []):
            visit(target)
        visiting.pop()
        done.add(node)

    for node in list(adjacency):
        visit(node)
    return cycles


def validate_graph(graph: dict[str, Any], graph_path: Path | None = None) -> dict[str, Any]:
    config = load_config(graph_path) if graph_path else {}
    node_types, relations = allowed_node_types(config), allowed_relations(config)
    issues: list[ValidationIssue] = []
    nodes, edges = graph.get("nodes") or {}, graph.get("edges") or []
    version = graph_version(graph)
    if version not in (1, 2):
        issues.append(ValidationIssue("error", "unsupported_version", f"unsupported schema version {version}"))

    for nid, node in nodes.items():
        if node.get("id") != nid:
            issues.append(ValidationIssue("error", "id_mismatch", f"node key {nid!r} != node.id {node.get('id')!r}", node_id=nid))
        if node.get("type") not in node_types:
            issues.append(ValidationIssue("error", "unknown_type", f"unknown node type {node.get('type')!r}", node_id=nid))
        for field, allowed in (("status", TRUTH_STATUSES), ("workflow_state", WORKFLOW_STATES), ("verification", VERIFICATION_STATES)):
            value = node.get(field)
            if value and value not in allowed:
                issues.append(ValidationIssue("error", f"unknown_{field}", f"unknown {field} {value!r}", node_id=nid))
        bad_stages = sorted(node_stages(node) - LIFECYCLE_STAGES)
        if bad_stages:
            issues.append(ValidationIssue("error", "unknown_stage", f"unknown stage(s) {bad_stages}", node_id=nid))
        for field in ("created_at", "updated_at", "started_at", "completed_at", "due_at", "finalized_at"):
            if node.get(field) is not None and not _timestamp_ok(node[field]):
                issues.append(ValidationIssue("error", "invalid_timestamp", f"invalid {field}", node_id=nid, field=field))
        if node.get("finalized_at") and node.get("created_at") and node["finalized_at"] < node["created_at"]:
            issues.append(ValidationIssue("error", "impossible_finalization", "finalized_at predates created_at", node_id=nid))
        if node.get("started_at") and node.get("completed_at") and node["completed_at"] < node["started_at"]:
            issues.append(ValidationIssue("error", "impossible_dates", "completed_at predates started_at", node_id=nid))
        evidence = node.get("evidence") or []
        if not isinstance(evidence, list):
            issues.append(ValidationIssue("error", "invalid_evidence", "evidence must be a list", node_id=nid))
        else:
            for index, item in enumerate(evidence):
                if not isinstance(item, dict) or item.get("type") not in EVIDENCE_TYPES or not item.get("ref"):
                    issues.append(ValidationIssue("error", "invalid_evidence", "evidence requires a built-in type and ref", node_id=nid, evidence_index=index))
        scope = node.get("scope") or {}
        if not isinstance(scope, dict):
            issues.append(ValidationIssue("error", "invalid_scope", "scope must be an object", node_id=nid))
        provenance = node.get("provenance") or {}
        if not isinstance(provenance, dict):
            issues.append(ValidationIssue("error", "invalid_provenance", "provenance must be an object", node_id=nid))
        else:
            integrity = provenance.get("integrity", "unknown")
            if integrity not in PROVENANCE_INTEGRITIES:
                issues.append(ValidationIssue("error", "invalid_provenance_integrity", f"unknown provenance integrity {integrity!r}", node_id=nid))
            if integrity == "verified" and not provenance.get("attestation_ref"):
                issues.append(ValidationIssue("error", "unattested_verified_provenance", "verified provenance requires an attestation_ref", node_id=nid))

    seen: set[tuple[Any, Any, Any]] = set()
    for index, edge in enumerate(edges):
        rel, frm, to = edge.get("rel"), edge.get("from"), edge.get("to")
        if rel not in relations:
            issues.append(ValidationIssue("warning", "unknown_relation", f"unknown relation {rel!r}", edge_index=index, rel=rel))
        if frm not in nodes:
            issues.append(ValidationIssue("error", "dangling_from", f"edge from missing node {frm!r}", edge_index=index))
        if to not in nodes:
            issues.append(ValidationIssue("error", "dangling_to", f"edge to missing node {to!r}", edge_index=index))
        key = (frm, to, rel)
        if key in seen:
            issues.append(ValidationIssue("error", "duplicate_edge", "duplicate directed relation", edge_index=index))
        seen.add(key)
        if rel == "supersedes" and frm == to:
            issues.append(ValidationIssue("error", "self_supersession", "node cannot supersede itself", edge_index=index))
        if edge.get("created_at") is not None and not _timestamp_ok(edge["created_at"]):
            issues.append(ValidationIssue("error", "invalid_timestamp", "invalid edge created_at", edge_index=index))

    for cycle in _relation_cycles(graph, {"supersedes"}):
        issues.append(ValidationIssue("error", "supersession_cycle", "supersession cycle detected", cycle=cycle))
    for nid, node in nodes.items():
        incoming, outgoing = superseded_by(graph, nid), supersedes_targets(graph, nid)
        status = (node.get("status") or "").lower()
        if status == "superseded" and not incoming:
            issues.append(ValidationIssue("warning", "superseded_no_edge", "node marked superseded but has no replacement", node_id=nid))
        if incoming and status not in ("superseded", "historical", "deprecated"):
            issues.append(ValidationIssue("warning", "superseded_status_mismatch", "superseded node still presents as current", node_id=nid, superseded_by=incoming))
        if len([x for x in incoming if (nodes.get(x) or {}).get("status") in ("current", "canonical_spec")]) > 1:
            issues.append(ValidationIssue("warning", "competing_replacements", "multiple current replacements supersede this node", node_id=nid, replacements=incoming))
        if outgoing and status not in ("current", "canonical_spec", "proposed"):
            issues.append(ValidationIssue("info", "supersedes_status_hint", "replacement should usually be current, canonical_spec, or proposed", node_id=nid))

    errors = [issue for issue in issues if issue.level in ("error", "critical")]
    return {"valid": not errors, "version": version, "nodes": len(nodes), "edges": len(edges),
            "issues": [issue.to_dict() for issue in issues], "error_count": len(errors),
            "warning_count": sum(issue.level == "warning" for issue in issues)}


def audit_graph(graph: dict[str, Any], graph_path: Path | None = None) -> dict[str, Any]:
    graph = normalize_graph(graph)
    nodes, edges = graph.get("nodes") or {}, graph.get("edges") or []
    counts = {
        "by_type": Counter(n.get("type", "unknown") for n in nodes.values()),
        "by_status": Counter(n.get("status", "unclassified") for n in nodes.values()),
        "by_workflow_state": Counter(n.get("workflow_state", "not_applicable") for n in nodes.values()),
        "by_verification": Counter(n.get("verification", "unverified") for n in nodes.values()),
        "by_stage": Counter(stage for n in nodes.values() for stage in (node_stages(n) or {"unassigned"})),
        "by_provenance_integrity": Counter((n.get("provenance") or {}).get("integrity", "unknown") for n in nodes.values()),
        "by_rel": Counter(e.get("rel", "unknown") for e in edges),
    }
    degree = Counter()
    for edge in edges:
        degree[edge.get("from")] += 1
        degree[edge.get("to")] += 1
    isolated = [nid for nid in nodes if degree[nid] == 0]
    weak = [nid for nid in nodes if degree[nid] == 1]
    pending = [nid for nid, n in nodes.items() if (n.get("meta") or {}).get("status") == "pending" or ((n.get("meta") or {}).get("source") == "ingest" and not (n.get("content") or "").strip())]
    low_quality_ingest = [nid for nid, n in nodes.items()
                          if n.get("type") in ("image", "video", "audio")
                          and (n.get("meta") or {}).get("source") == "ingest"
                          and len((n.get("content") or "").strip()) < 40]
    verified_without_evidence = [nid for nid, n in nodes.items() if n.get("verification") == "verified" and not (n.get("evidence") or []) and not any(e.get("from") == nid and e.get("rel") in ("verified_by", "evidenced_by") for e in edges)]
    contradictions = [e for e in edges if e.get("rel") == "contradicts"]
    superseded_no_edge = [nid for nid, n in nodes.items() if n.get("status") == "superseded" and not superseded_by(graph, nid)]
    canonical_specs = [nid for nid, n in nodes.items() if n.get("status") == "canonical_spec"]
    current_findings = [nid for nid, n in nodes.items() if n.get("type") == "finding" and n.get("status") in ("current", "proposed")]

    stale_checkpoints: list[str] = []
    for nid, node in nodes.items():
        if node.get("type") != "checkpoint":
            continue
        sources = [e.get("to") for e in edges if e.get("from") == nid and e.get("rel") == "derived_from"]
        stale = any((nodes.get(src) or {}).get("updated_at", "") > node.get("updated_at", "") or
                    (nodes.get(src) or {}).get("status") in ("superseded", "rejected") or
                    (nodes.get(src) or {}).get("verification") == "failed" or
                    (nodes.get(src) or {}).get("provenance", {}).get("integrity") in ("contested", "invalidated")
                    for src in sources)
        stale = stale or any(e.get("rel") == "contradicts" and (e.get("from") in sources or e.get("to") in sources) for e in edges)
        if stale:
            stale_checkpoints.append(nid)

    dependency_cycles = _relation_cycles(graph, {"depends_on", "blocks"})

    mission_generations: dict[str, set[str]] = defaultdict(set)
    generation_states: dict[tuple[str, str], set[str]] = defaultdict(set)
    for node in nodes.values():
        scope = node.get("scope") or {}
        mission, generation = scope.get("mission_id"), scope.get("generation_id")
        if mission and generation:
            mission_generations[mission].add(generation)
            generation_states[(mission, generation)].add(node.get("workflow_state", "not_applicable"))
    generation_ambiguity = [mission for mission, generations in mission_generations.items() if len(generations) > 1 and any("active" in generation_states[(mission, generation)] for generation in generations) and any("completed" in generation_states[(mission, generation)] for generation in generations)]

    rel_counts = counts["by_rel"]
    related_pct = round(100.0 * rel_counts.get("related", 0) / len(edges), 1) if edges else 0.0
    issues = []
    for code, level, ids in (
        ("verified_without_evidence", "warning", verified_without_evidence),
        ("stale_checkpoint", "warning", stale_checkpoints),
        ("generation_ambiguity", "warning", generation_ambiguity),
        ("dependency_cycles", "warning", dependency_cycles),
        ("low_quality_ingest", "warning", low_quality_ingest),
        ("isolated_nodes", "info", isolated),
    ):
        if ids:
            issues.append({"level": level, "code": code, "count": len(ids), "sample": ids[:10]})
    from grapher.provenance import validate_history
    history = validate_history(graph_path) if graph_path else None
    return {
        "version": graph_version(graph), "graph_meta": graph.get("graph"),
        "history": history,
        "counts": {"nodes": len(nodes), "edges": len(edges), **{k: dict(v) for k, v in counts.items()}},
        "health": {"related_pct": related_pct, "related_heavy": related_pct > 40,
                   "pending_ingest": len(pending), "low_quality_ingest": len(low_quality_ingest), "isolated_nodes": len(isolated),
                   "weakly_connected_nodes": len(weak), "superseded_no_edge": len(superseded_no_edge),
                   "contradictions": len(contradictions), "dependency_cycles": len(dependency_cycles), "verified_without_evidence": len(verified_without_evidence),
                   "stale_checkpoints": len(stale_checkpoints), "generation_ambiguity": len(generation_ambiguity),
                   "canonical_specs": len(canonical_specs), "current_findings": len(current_findings)},
        "issues": issues,
        "samples": {"pending_ingest": pending[:10], "low_quality_ingest": low_quality_ingest[:10], "isolated_nodes": isolated[:10],
                    "superseded_no_edge": superseded_no_edge[:10], "canonical_specs": canonical_specs[:10],
                    "stale_checkpoints": stale_checkpoints[:10], "generation_ambiguity": generation_ambiguity[:10], "dependency_cycles": dependency_cycles[:10]},
        "validation": validate_graph(graph, graph_path),
    }
