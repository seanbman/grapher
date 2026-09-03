"""Shared query filtering and truth-aware ranking."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from grapher.registry import (
    STATUS_RANK_WEIGHTS,
    TRUTH_STATUSES,
    VERIFICATION_RANK_BOOST,
    normalize_stage,
)


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_status_filter(raw: str | None) -> set[str] | None:
    if not raw:
        return None
    parts = {p.strip().lower() for p in raw.split(",") if p.strip()}
    return parts or None


def parse_stage_filter(raw: str | None) -> set[str] | None:
    if not raw:
        return None
    parts = {normalize_stage(p) for p in raw.split(",") if p.strip()}
    return parts or None


def node_stages(node: dict[str, Any]) -> set[str]:
    stage = node.get("stage")
    if stage is None:
        return set()
    if isinstance(stage, str):
        return {normalize_stage(stage)}
    if isinstance(stage, list):
        return {normalize_stage(str(s)) for s in stage if str(s).strip()}
    return set()


def matches_filters(
    node: dict[str, Any],
    *,
    type: str | None = None,
    tag: str | None = None,
    status: set[str] | None = None,
    stage: set[str] | None = None,
    verification: str | None = None,
    workflow_state: str | None = None,
    project: str | None = None,
    mission: str | None = None,
    generation: str | None = None,
    actor: str | None = None,
    role: str | None = None,
    as_of: str | None = None,
    exclude_superseded: bool = False,
    current_only: bool = False,
) -> bool:
    if type and node.get("type") != type:
        return False
    if tag and tag not in (node.get("tags") or []):
        return False
    node_status = (node.get("status") or "unclassified").lower()
    if current_only and node_status not in ("current", "canonical_spec", "proposed"):
        return False
    if exclude_superseded and node_status in ("superseded", "rejected", "deprecated"):
        return False
    if status and node_status not in status:
        return False
    if verification and (node.get("verification") or "unverified") != verification:
        return False
    if workflow_state and (node.get("workflow_state") or "not_applicable") != workflow_state:
        return False
    if stage:
        ns = node_stages(node)
        if not ns or not (ns & stage):
            return False
    scope = node.get("scope") or {}
    provenance = node.get("provenance") or {}
    if project and scope.get("project_id") != project:
        return False
    if mission and scope.get("mission_id") != mission:
        return False
    if generation and scope.get("generation_id") != generation:
        return False
    if actor and provenance.get("actor_id") != actor:
        return False
    if role and provenance.get("actor_role") != role:
        return False
    if as_of:
        cutoff = _parse_timestamp(as_of)
        created = _parse_timestamp(node.get("created_at"))
        if cutoff is None:
            raise ValueError(f"invalid --as-of timestamp {as_of!r}")
        if created is not None and created > cutoff:
            return False
    return True


def truth_rank_factors(
    node: dict[str, Any], config: dict[str, Any] | None = None, *,
    query: str = "", project: str | None = None, mission: str | None = None,
    generation: str | None = None,
) -> tuple[float, dict[str, float]]:
    weights = dict(STATUS_RANK_WEIGHTS)
    custom = (config or {}).get("status_rank_weights") or {}
    weights.update(custom)
    status = (node.get("status") or "unclassified").lower()
    base = weights.get(status, 0.5)
    ver = (node.get("verification") or "unverified").lower()
    verification_adjustment = VERIFICATION_RANK_BOOST.get(ver, 0.0)
    integrity = (node.get("provenance") or {}).get("integrity", "unknown")
    authoritative = any(word in query.lower() for word in ("current", "now", "accepted", "complete", "authoritative", "state"))
    provenance_adjustment = {"verified": 0.08, "declared": 0.03, "unknown": 0.0,
                             "contested": -0.12, "invalidated": -0.25}.get(integrity, 0.0)
    if not authoritative:
        provenance_adjustment *= 0.35
    scope = node.get("scope") or {}
    scope_adjustment = 0.0
    for wanted, key in ((project, "project_id"), (mission, "mission_id"),
                        (generation, "generation_id")):
        if wanted:
            scope_adjustment += 0.08 if scope.get(key) == wanted else -0.12
    q = query.lower()
    intent_adjustment = 0.0
    if any(x in q for x in ("original requirement", "canonical spec", "policy")) and status == "canonical_spec":
        intent_adjustment += 0.18
    if any(x in q for x in ("why", "failure", "root cause", "incident")):
        if status == "historical" or node.get("type") in ("incident", "audit_record"):
            intent_adjustment += 0.55
    if any(x in q for x in ("plan", "next", "future", "roadmap")):
        if status == "proposed" or node.get("workflow_state") == "active":
            intent_adjustment += 0.4
    if authoritative and status == "current":
        intent_adjustment += 1.0
    checkpoint_adjustment = 0.04 if node.get("type") == "checkpoint" and status == "current" else 0.0
    total = base + verification_adjustment + provenance_adjustment + scope_adjustment + intent_adjustment + checkpoint_adjustment
    return total, {"status_adjustment": base,
                   "verification_adjustment": verification_adjustment,
                   "provenance_adjustment": provenance_adjustment,
                   "scope_adjustment": scope_adjustment,
                   "query_intent_adjustment": intent_adjustment,
                   "checkpoint_adjustment": checkpoint_adjustment,
                   "stage_match": 0.0, "kind_match": 0.0,
                   "recency_component": 0.0, "edge_context_component": 0.0}


def truth_rank_boost(node: dict[str, Any], config: dict[str, Any] | None = None) -> float:
    """Backward-compatible scalar truth boost for library callers."""
    return truth_rank_factors(node, config)[0]


def apply_truth_ranking(
    hits: list[dict[str, Any]],
    *,
    config: dict[str, Any] | None = None,
    explain: bool = False,
    query: str = "", project: str | None = None, mission: str | None = None,
    generation: str | None = None,
) -> list[dict[str, Any]]:
    ranked: list[tuple[float, dict[str, Any]]] = []
    for hit in hits:
        node = hit["node"]
        base = float(hit.get("score", 0.0))
        boost, factors = truth_rank_factors(
            node, config, query=query, project=project, mission=mission, generation=generation
        )
        authoritative = any(word in query.lower() for word in ("current", "now", "accepted", "complete", "authoritative", "state"))
        semantic_weight = 0.65 if authoritative else 0.85
        final = round(base * semantic_weight + boost * (1.0 - semantic_weight), 4)
        out = dict(hit)
        out["score"] = final
        if explain:
            out["ranking"] = {
                "base_score": hit.get("score"),
                "truth_boost": round(boost, 4),
                "status": node.get("status"),
                "verification": node.get("verification"),
                **factors,
                "semantic_score": hit.get("semantic_score", hit.get("score")),
                "semantic_weight": semantic_weight,
                "final_score": final,
            }
        ranked.append((final, out))
    ranked.sort(key=lambda x: (-x[0], x[1]["node"].get("title") or ""))
    return [h for _, h in ranked]


def superseded_by(graph: dict[str, Any], node_id: str) -> list[str]:
    """Return ids of nodes that supersede this one (incoming supersedes edges)."""
    out: list[str] = []
    for e in graph.get("edges") or []:
        if e.get("rel") == "supersedes" and e.get("to") == node_id:
            out.append(e["from"])
    return out


def supersedes_targets(graph: dict[str, Any], node_id: str) -> list[str]:
    out: list[str] = []
    for e in graph.get("edges") or []:
        if e.get("rel") == "supersedes" and e.get("from") == node_id:
            out.append(e["to"])
    return out


def infer_status_from_content(content: str) -> str | None:
    """Deprecated: use grapher.infer.infer_status for context-aware inference."""
    from grapher.infer import infer_status

    status, _ = infer_status(content)
    return status


def infer_stage_from_tags(tags: list[str]) -> list[str] | None:
    mapping = {
        "ideation": "ideation",
        "design": "designing",
        "designing": "designing",
        "planning": "planning",
        "development": "developing",
        "developing": "developing",
        "launch": "launching",
        "launching": "launching",
        "maintenance": "maintaining",
        "maintaining": "maintaining",
        "ops": "maintaining",
        "operations": "maintaining",
    }
    stages: list[str] = []
    for t in tags:
        key = t.strip().lower()
        if key in mapping and mapping[key] not in stages:
            stages.append(mapping[key])
    return stages or None


def infer_stage_from_type(node_type: str) -> str | None:
    if node_type in ("finding", "incident", "issue"):
        return "developing"
    if node_type in ("image", "document", "artifact"):
        return "designing"
    if node_type in ("instruction", "policy"):
        return "maintaining"
    if node_type in ("decision", "option"):
        return "planning"
    if node_type in ("milestone", "deliverable"):
        return "planning"
    return None
