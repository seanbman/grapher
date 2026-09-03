"""Context-aware metadata inference with auditable explanations."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from grapher.registry import CANONICAL_STAGE_ORDER, normalize_stage


@dataclass
class InferenceRecord:
    node_id: str
    status: str | None = None
    verification: str | None = None
    stage: list[str] | None = None
    evidence: list[dict[str, Any]] = field(default_factory=list)
    new_edges: list[dict[str, Any]] = field(default_factory=list)
    explanations: list[str] = field(default_factory=list)
    confidence: str = "low"  # low | medium | high

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "status": self.status,
            "verification": self.verification,
            "stage": self.stage,
            "evidence": self.evidence,
            "new_edges": self.new_edges,
            "explanations": self.explanations,
            "confidence": self.confidence,
        }


# --- status patterns (order matters: first match wins) ---

_SUPERSEDED_BY = re.compile(
    r"^SUPERSEDED\s+by\s+([a-z0-9][a-z0-9-]+)",
    re.IGNORECASE | re.MULTILINE,
)
_TITLE_SUPERSEDED = re.compile(r"\(superseded\)", re.IGNORECASE)
_CONFIRMED_FIX = re.compile(
    r"(?:\bCONFIRMED\b.*\bFix:|\bFix:.*\bVerified\b|\bVerified\b.*\bheadless\b)",
    re.IGNORECASE | re.DOTALL,
)
_IMPLEMENTED = re.compile(
    r"(?:^|\n)\s*(?:[-*]\s*)?(?:implemented|shipped|landed)\b|"
    r"\bimplemented\s+(?:Sep|Oct|Nov|Dec|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug)\b|"
    r"\b(?:was|were)\s+\w+[^.]{0,40}\.\s*Now\s+\w+",  # bug description → "Now fix..."
    re.IGNORECASE,
)
_HYPOTHESIS_REJECTED = re.compile(
    r"Hypotheses?\s+.+?\bREJECTED\b",
    re.IGNORECASE | re.DOTALL,
)
_LINE_REJECTED = re.compile(
    r"^(?:Status|Verdict|Decision):\s*REJECTED\b",
    re.IGNORECASE | re.MULTILINE,
)
_LEGACY_DESIGN = re.compile(
    r"\b(?:legacy design|legacy architecture|original design)\b",
    re.IGNORECASE,
)
_LEGACY_FIELDS = re.compile(r"\blegacy fields\b", re.IGNORECASE)
_PROPOSED_LINE = re.compile(
    r"^(?:PROPOSED|Draft plan|Status:\s*proposed)\b",
    re.IGNORECASE | re.MULTILINE,
)
_CURRENT_LINE = re.compile(
    r"^(?:CURRENT|Status:\s*current)\b",
    re.IGNORECASE | re.MULTILINE,
)
# "current Shape" / "current settings" — adjective use, not truth status
_CURRENT_ADJECTIVE = re.compile(
    r"\bcurrent\s+(?:shape|env|eq|fx|state|settings|value|pattern|kit|sound|preset)\b",
    re.IGNORECASE,
)
_DRAFT_UI = re.compile(r"\bdraft peaks\b|\bdraft state\b", re.IGNORECASE)


def infer_status(
    content: str,
    *,
    title: str = "",
    node_type: str = "",
) -> tuple[str | None, list[str]]:
    """Return (status, explanations). None means leave unclassified."""
    explanations: list[str] = []
    if not content and not title:
        return None, explanations

    # Reference artifacts should not inherit truth status from descriptive text
    if node_type in ("image", "video", "audio"):
        if _TITLE_SUPERSEDED.search(title):
            explanations.append("title contains (superseded)")
            return "superseded", explanations
        if _SUPERSEDED_BY.search(content):
            explanations.append("content declares SUPERSEDED by another node")
            return "superseded", explanations
        explanations.append(f"type {node_type!r}: skip content keyword status inference")
        return None, explanations

    m = _SUPERSEDED_BY.search(content)
    if m:
        explanations.append(f"content starts with SUPERSEDED by {m.group(1)}")
        return "superseded", explanations

    if _TITLE_SUPERSEDED.search(title):
        explanations.append("title contains (superseded)")
        return "superseded", explanations

    if _CONFIRMED_FIX.search(content):
        explanations.append("confirmed root cause with documented fix and verification")
        return "historical", explanations

    if _IMPLEMENTED.search(content) or _IMPLEMENTED.search(title):
        explanations.append("documents implemented/shipped work")
        return "current", explanations

    if _HYPOTHESIS_REJECTED.search(content) and _CONFIRMED_FIX.search(content):
        explanations.append("hypotheses rejected but root cause confirmed — not node-level rejected")
        return "historical", explanations

    if _LINE_REJECTED.search(content):
        explanations.append("explicit Status/Verdict: REJECTED line")
        return "rejected", explanations

    if _LEGACY_DESIGN.search(content) and not _IMPLEMENTED.search(content):
        explanations.append("describes legacy/original design without current implementation")
        return "historical", explanations

    if _LEGACY_FIELDS.search(content):
        explanations.append("mentions legacy fields in passing — not marking historical")
        return None, explanations

    if _PROPOSED_LINE.search(content):
        explanations.append("explicit PROPOSED/Draft plan at line start")
        return "proposed", explanations

    if _DRAFT_UI.search(content):
        explanations.append("draft peaks/state is UI terminology — not proposed status")

    if _CURRENT_LINE.search(content):
        explanations.append("explicit CURRENT/Status: current line")
        return "current", explanations

    if re.search(r"\bCURRENT\b", content, re.IGNORECASE):
        if _CURRENT_ADJECTIVE.search(content):
            explanations.append("CURRENT matched adjective phrase (e.g. current Shape) — ignored")
            return None, explanations

    return None, explanations


def infer_verification(content: str, *, title: str = "") -> tuple[str | None, list[str]]:
    explanations: list[str] = []
    text = f"{title}\n{content}"
    if re.search(r"\bVerified\b.*\bheadless\b|\bheadless\b.*\bVerified\b", text, re.I):
        explanations.append("headless verification documented")
        return "verified", explanations
    if re.search(r"\bsmoke[- ]test\b|\bplaywright\b.*\bpass\b", text, re.I):
        explanations.append("smoke test results documented")
        return "verified", explanations
    if re.search(r"\bCONFIRMED\b", text) and re.search(r"\bFix:", text):
        explanations.append("confirmed fix with runtime evidence")
        return "verified", explanations
    if re.search(r"\bpartially verified\b|\bneeds manual\b", text, re.I):
        return "partially_verified", explanations
    return None, explanations


def infer_stage(
    content: str,
    *,
    title: str = "",
    tags: list[str] | None = None,
    node_type: str = "",
) -> tuple[list[str] | None, list[str]]:
    explanations: list[str] = []
    tags = tags or []
    text = f"{title}\n{content}".lower()

    if any(t in tags for t in ("roadmap", "milestone", "planning")) or "roadmap" in title.lower():
        explanations.append("roadmap/planning tag or title")
        return ["planning"], explanations

    if any(w in text for w in ("crash", "incident", "persist storm", "root cause", "bugfix")):
        explanations.append("incident/debug content")
        return ["maintaining"], explanations

    if node_type == "instruction" or "rule of thumb" in text:
        explanations.append("operating rule / instruction")
        return ["maintaining"], explanations

    if node_type == "concept":
        if title.lower().startswith("screen ") or "operating manual" in text:
            explanations.append("screen/manual concept")
            return ["designing"], explanations
        explanations.append("concept without clear lifecycle signal — leave unset")
        return None, explanations

    if node_type in ("image", "document"):
        explanations.append("reference artifact")
        return ["designing"], explanations

    if node_type == "finding":
        if "implemented" in text or "fix:" in text:
            explanations.append("implementation finding")
            return ["developing"], explanations
        explanations.append("finding default")
        return ["developing"], explanations

    tag_map = {
        "ideation": "ideation",
        "design": "designing",
        "planning": "planning",
        "development": "developing",
        "launch": "launching",
        "maintenance": "maintaining",
        "operations": "maintaining",
    }
    from_tags = []
    for t in tags:
        key = t.strip().lower()
        if key in tag_map and tag_map[key] not in from_tags:
            from_tags.append(tag_map[key])
    if from_tags:
        explanations.append(f"from tags: {tags}")
        return from_tags, explanations

    return None, explanations


def infer_supersedes_edges(
    node_id: str,
    content: str,
    *,
    nodes: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Edges where this node supersedes another (from SUPERSEDED BY in target content)."""
    edges: list[dict[str, Any]] = []
    explanations: list[str] = []
    for tid, target in nodes.items():
        if tid == node_id:
            continue
        m = _SUPERSEDED_BY.search(target.get("content") or "")
        if m and m.group(1).lower() == node_id.lower():
            edges.append(
                {
                    "from": node_id,
                    "to": tid,
                    "rel": "supersedes",
                    "note": "inferred from target SUPERSEDED BY declaration",
                }
            )
            explanations.append(f"target {tid} declares SUPERSEDED by this node")
    return edges, explanations


def infer_evidence(content: str) -> tuple[list[dict[str, Any]], list[str]]:
    evidence: list[dict[str, Any]] = []
    explanations: list[str] = []
    if re.search(r"\bRuntime evidence:", content, re.I):
        evidence.append(
            {
                "type": "observation",
                "ref": "runtime",
                "summary": "Runtime evidence cited in finding",
            }
        )
        explanations.append("runtime evidence mentioned")
    if re.search(r"\bVerified headless\b", content, re.I):
        evidence.append(
            {
                "type": "test",
                "ref": "headless",
                "summary": "Headless verification run documented",
            }
        )
        explanations.append("headless test evidence")
    return evidence, explanations


def infer_node(
    node_id: str,
    node: dict[str, Any],
    *,
    all_nodes: dict[str, Any] | None = None,
) -> InferenceRecord:
    content = node.get("content") or ""
    title = node.get("title") or ""
    node_type = node.get("type") or ""
    tags = node.get("tags") or []

    rec = InferenceRecord(node_id=node_id)

    status, sx = infer_status(content, title=title, node_type=node_type)
    rec.status = status
    rec.explanations.extend(sx)

    ver, vx = infer_verification(content, title=title)
    rec.verification = ver
    rec.explanations.extend(vx)

    stage, stx = infer_stage(content, title=title, tags=tags, node_type=node_type)
    rec.stage = stage
    rec.explanations.extend(stx)

    ev, evx = infer_evidence(content)
    rec.evidence = ev
    rec.explanations.extend(evx)

    if all_nodes:
        edges, ex = infer_supersedes_edges(node_id, content, nodes=all_nodes)
        rec.new_edges.extend(edges)
        rec.explanations.extend(ex)

        # Node referenced as superseder by others → current
        superseder_of = [e["to"] for e in edges if e["rel"] == "supersedes"]
        if superseder_of and not rec.status:
            rec.status = "current"
            rec.explanations.append(
                f"other node(s) declare SUPERSEDED by this node: {superseder_of}"
            )
            rec.confidence = "high"

    if rec.status or rec.verification or rec.new_edges:
        rec.confidence = "high" if rec.new_edges or _SUPERSEDED_BY.search(content) else "medium"
    elif rec.stage:
        rec.confidence = "low"

    return rec


def preview_inference(graph: dict[str, Any]) -> dict[str, Any]:
    nodes = graph.get("nodes") or {}
    records: list[InferenceRecord] = []
    edge_candidates: list[dict[str, Any]] = []

    for nid, node in nodes.items():
        rec = infer_node(nid, node, all_nodes=nodes)
        if rec.status or rec.verification or rec.stage or rec.evidence or rec.new_edges:
            records.append(rec)
        edge_candidates.extend(rec.new_edges)

    # Dedupe proposed supersedes edges
    seen: set[tuple[str, str, str]] = set()
    unique_edges: list[dict[str, Any]] = []
    for e in edge_candidates:
        key = (e["from"], e["to"], e["rel"])
        if key not in seen:
            seen.add(key)
            unique_edges.append(e)

    status_counts: dict[str, int] = {}
    for r in records:
        if r.status:
            status_counts[r.status] = status_counts.get(r.status, 0) + 1

    return {
        "action": "infer_preview",
        "nodes_total": len(nodes),
        "nodes_with_inferences": len(records),
        "status_counts": status_counts,
        "proposed_edges": len(unique_edges),
        "records": [r.to_dict() for r in records],
        "edges": unique_edges,
    }


def apply_inference(
    graph: dict[str, Any],
    *,
    only_high_confidence: bool = False,
    include_stages: bool = True,
    include_edges: bool = True,
) -> dict[str, Any]:
    """Apply previewed inference to graph in place. Returns summary."""
    preview = preview_inference(graph)
    applied_nodes = 0
    applied_edges = 0
    skipped = 0

    for raw in preview["records"]:
        if only_high_confidence and raw.get("confidence") != "high":
            skipped += 1
            continue
        node = graph["nodes"].get(raw["node_id"])
        if not node:
            continue
        changed = False
        if raw.get("status"):
            node["status"] = raw["status"]
            changed = True
        if raw.get("verification"):
            node["verification"] = raw["verification"]
            changed = True
        if include_stages and raw.get("stage"):
            node["stage"] = raw["stage"]
            changed = True
        if raw.get("evidence"):
            node["evidence"] = raw["evidence"]
            changed = True
        meta = dict(node.get("meta") or {})
        meta["inference"] = {
            "explanations": raw.get("explanations") or [],
            "confidence": raw.get("confidence"),
        }
        node["meta"] = meta
        if changed:
            applied_nodes += 1

    if include_edges:
        existing = {
            (e.get("from"), e.get("to"), e.get("rel"))
            for e in graph.get("edges") or []
        }
        from grapher.model import make_edge, now_iso

        for e in preview["edges"]:
            key = (e["from"], e["to"], e["rel"])
            if key in existing:
                continue
            graph.setdefault("edges", []).append(
                make_edge(
                    from_id=e["from"],
                    to_id=e["to"],
                    rel=e["rel"],
                    note=e.get("note"),
                )
            )
            existing.add(key)
            applied_edges += 1

    return {
        "action": "infer_apply",
        "applied_nodes": applied_nodes,
        "applied_edges": applied_edges,
        "skipped_low_confidence": skipped,
        "preview": preview,
    }


def reset_truth_metadata(graph: dict[str, Any]) -> dict[str, Any]:
    """Strip inferred truth fields; keep v2 schema and original content."""
    from grapher.model import DEFAULT_NODE_STATUS, DEFAULT_VERIFICATION, DEFAULT_WORKFLOW_STATE

    reset = 0
    for node in graph.get("nodes", {}).values():
        for field in ("status", "verification", "stage", "evidence", "source_refs", "owners"):
            if field in node:
                node.pop(field, None)
                reset += 1
        meta = dict(node.get("meta") or {})
        meta.pop("inference", None)
        node["meta"] = meta
        node["status"] = DEFAULT_NODE_STATUS
        node["workflow_state"] = DEFAULT_WORKFLOW_STATE
        node["verification"] = DEFAULT_VERIFICATION
        node["evidence"] = []
        node["source_refs"] = []
        node["owners"] = []

    # Remove inferred supersedes edges only (keep all other edges)
    before = len(graph.get("edges") or [])
    graph["edges"] = [
        e
        for e in graph.get("edges") or []
        if not (
            e.get("rel") == "supersedes"
            and (e.get("note") or "").startswith("inferred")
        )
    ]
    removed_edges = before - len(graph["edges"])

    return {
        "action": "reset_truth",
        "nodes_reset": len(graph.get("nodes") or {}),
        "fields_cleared": reset,
        "inferred_edges_removed": removed_edges,
    }


def sort_stages(stages: list[str]) -> list[str]:
    order = {s: i for i, s in enumerate(CANONICAL_STAGE_ORDER)}
    return sorted(set(normalize_stage(s) for s in stages), key=lambda s: order.get(s, 99))
