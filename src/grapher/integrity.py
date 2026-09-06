"""Tamper-evident semantic identity and immutable status transition records."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

SEMANTIC_HASH_ALGORITHM = "sha256"
SEMANTIC_HASH_SCHEME = "grapher-semantic-v1"
STATUS_TRANSITION_TYPE = "status_transition"
STATUS_TRANSITION_REL = "status_changed_by"


def _canonical_content(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    text = value.replace("\r\n", "\n").replace("\r", "\n")
    stripped = text.strip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass
    return text


def _sorted_json_values(values: list[Any]) -> list[Any]:
    return sorted(
        values,
        key=lambda value: json.dumps(
            value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ),
    )


def semantic_nucleus(node: dict[str, Any]) -> dict[str, Any]:
    """Return the canonical semantic assertion protected by the node hash.

    Truth/workflow/lifecycle state is deliberately excluded. Those fields describe
    how an assertion is currently treated, not what the assertion means.
    """
    tags = sorted(str(tag) for tag in (node.get("tags") or []))
    source_refs = sorted(str(ref) for ref in (node.get("source_refs") or []))
    evidence = _sorted_json_values(list(node.get("evidence") or []))
    return {
        "type": node.get("type"),
        "title": node.get("title"),
        "content": _canonical_content(node.get("content") or ""),
        "tags": tags,
        "evidence": evidence,
        "source_refs": source_refs,
        "scope": dict(node.get("scope") or {}),
        "provenance": dict(node.get("provenance") or {}),
        "created_at": node.get("created_at"),
    }


def semantic_hash(node: dict[str, Any]) -> str:
    raw = json.dumps(
        semantic_nucleus(node),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def seal_node(node: dict[str, Any]) -> dict[str, str]:
    """Attach or refresh the canonical semantic integrity record."""
    record = {
        "algorithm": SEMANTIC_HASH_ALGORITHM,
        "scheme": SEMANTIC_HASH_SCHEME,
        "semantic_hash": semantic_hash(node),
    }
    node["integrity"] = record
    return record


def verify_node_integrity(node: dict[str, Any]) -> dict[str, Any]:
    integrity = node.get("integrity") or {}
    if not integrity:
        return {"valid": False, "reason": "missing_integrity", "actual": semantic_hash(node)}
    if integrity.get("algorithm") != SEMANTIC_HASH_ALGORITHM:
        return {"valid": False, "reason": "unsupported_algorithm", "integrity": integrity}
    if integrity.get("scheme") != SEMANTIC_HASH_SCHEME:
        return {"valid": False, "reason": "unsupported_scheme", "integrity": integrity}
    expected = integrity.get("semantic_hash")
    actual = semantic_hash(node)
    return {
        "valid": expected == actual,
        "reason": None if expected == actual else "semantic_hash_mismatch",
        "expected": expected,
        "actual": actual,
    }


def seal_finalized_nodes(graph: dict[str, Any]) -> list[str]:
    """Ensure finalized records have a valid semantic seal.

    Missing seals are bootstrapped for pre-integrity finalized records. Existing
    seals are never silently replaced when they fail validation.
    """
    sealed: list[str] = []
    for node_id, node in (graph.get("nodes") or {}).items():
        if not node.get("finalized_at"):
            continue
        if not node.get("integrity"):
            seal_node(node)
            sealed.append(node_id)
            continue
        result = verify_node_integrity(node)
        if not result["valid"]:
            raise ValueError(
                f"semantic integrity mismatch for finalized node {node_id!r}; "
                "preserve the record and create a correcting/superseding node"
            )
    return sealed


def _actor_provenance(actor: dict[str, Any] | None) -> dict[str, Any]:
    actor = actor or {}
    provenance = {
        "actor_id": actor.get("id") or actor.get("actor_id"),
        "actor_kind": actor.get("kind") or actor.get("actor_kind"),
        "actor_role": actor.get("role") or actor.get("actor_role"),
        "session_id": actor.get("session_id"),
        "source": actor.get("source"),
    }
    return {key: value for key, value in provenance.items() if value is not None}


def status_transition_payload(node: dict[str, Any]) -> dict[str, Any]:
    if node.get("type") != STATUS_TRANSITION_TYPE:
        raise ValueError(f"node {node.get('id')!r} is not a status transition")
    try:
        payload = json.loads(node.get("content") or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid status transition content: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("status transition content must be a JSON object")
    return payload


def status_transition_nodes(graph: dict[str, Any], subject_id: str) -> list[dict[str, Any]]:
    transition_ids = {
        edge.get("to")
        for edge in (graph.get("edges") or [])
        if edge.get("from") == subject_id and edge.get("rel") == STATUS_TRANSITION_REL
    }
    nodes = [
        node
        for node_id, node in (graph.get("nodes") or {}).items()
        if node_id in transition_ids and node.get("type") == STATUS_TRANSITION_TYPE
    ]
    return sorted(nodes, key=lambda node: (node.get("created_at") or "", node.get("id") or ""))


def effective_status(graph: dict[str, Any], subject_id: str) -> str:
    subject = (graph.get("nodes") or {}).get(subject_id)
    if subject is None:
        raise KeyError(subject_id)
    transitions = status_transition_nodes(graph, subject_id)
    if not transitions:
        return str(subject.get("status") or "unclassified")
    return str(status_transition_payload(transitions[-1]).get("to_status") or subject.get("status") or "unclassified")


def _status_transition_reason(
    after: dict[str, Any],
    subject: dict[str, Any],
    *,
    old_status: str,
    new_status: str,
    explicit_reason: str | None,
    operation_id: str,
) -> str:
    if explicit_reason and explicit_reason.strip():
        return explicit_reason.strip()

    inference = (subject.get("meta") or {}).get("inference") or {}
    explanations = [str(item).strip() for item in (inference.get("explanations") or []) if str(item).strip()]
    if explanations:
        return "Inference: " + "; ".join(explanations)

    subject_id = subject.get("id")
    for edge in after.get("edges") or []:
        if edge.get("rel") == "supersedes" and edge.get("to") == subject_id:
            note = str(edge.get("note") or "").strip()
            replacement = edge.get("from")
            if note:
                return f"Superseded by {replacement}: {note}"
            return f"Superseded by {replacement}."

    return f"Truth status changed from {old_status} to {new_status} during {operation_id}."


def materialize_status_transitions(
    before: dict[str, Any] | None,
    after: dict[str, Any],
    *,
    actor: dict[str, Any] | None,
    reason: str | None,
    operation_id: str,
) -> list[str]:
    """Turn status field changes into immutable child records inside the graph."""
    from grapher.graph import add_node, link
    from grapher.model import now_iso

    old_nodes = (before or {}).get("nodes") or {}
    new_nodes = after.get("nodes") or {}
    created: list[str] = []

    for node_id in sorted(set(old_nodes) & set(new_nodes)):
        previous = old_nodes[node_id]
        subject = new_nodes[node_id]
        old_status = str(previous.get("status") or "unclassified")
        new_status = str(subject.get("status") or "unclassified")
        if old_status == new_status:
            continue

        # A classified assertion crosses the immutable semantic boundary. Status
        # itself remains a derived/cache field and is intentionally not hashed.
        if not subject.get("integrity"):
            seal_node(subject)
        else:
            check = verify_node_integrity(subject)
            if not check["valid"]:
                raise ValueError(
                    f"semantic integrity mismatch for node {node_id!r} during status transition"
                )
        if not subject.get("finalized_at"):
            subject["finalized_at"] = now_iso()

        rationale = _status_transition_reason(
            after,
            subject,
            old_status=old_status,
            new_status=new_status,
            explicit_reason=reason,
            operation_id=operation_id,
        )
        payload = {
            "subject_hash": semantic_hash(subject),
            "from_status": old_status,
            "to_status": new_status,
            "reason": rationale,
            "operation_id": operation_id,
        }
        transition = add_node(
            after,
            type=STATUS_TRANSITION_TYPE,
            title=f"Status transition: {subject.get('title') or node_id} → {new_status}",
            content=json.dumps(payload, sort_keys=True, ensure_ascii=False),
            status="current",
            workflow_state="not_applicable",
            verification="not_applicable",
            provenance=_actor_provenance(actor) or None,
        )
        seal_node(transition)
        transition["finalized_at"] = now_iso()
        transition["updated_at"] = transition["finalized_at"]
        link(
            after,
            from_id=node_id,
            to_id=transition["id"],
            rel=STATUS_TRANSITION_REL,
            note="immutable truth-status transition",
        )
        created.append(transition["id"])
    return created


def validate_graph_integrity(graph: dict[str, Any]) -> dict[str, Any]:
    """Validate semantic seals, transition hashes, child links, and status cache."""
    issues: list[dict[str, Any]] = []
    nodes = graph.get("nodes") or {}
    edges = graph.get("edges") or []

    for node_id, node in nodes.items():
        if node.get("finalized_at"):
            result = verify_node_integrity(node)
            if not result["valid"]:
                issues.append({"code": result["reason"], "node_id": node_id})

    for transition_id, transition in nodes.items():
        if transition.get("type") != STATUS_TRANSITION_TYPE:
            continue
        try:
            payload = status_transition_payload(transition)
        except ValueError as exc:
            issues.append({"code": "invalid_status_transition", "node_id": transition_id, "message": str(exc)})
            continue
        subject_ids = [
            edge.get("from")
            for edge in edges
            if edge.get("to") == transition_id and edge.get("rel") == STATUS_TRANSITION_REL
        ]
        if len(subject_ids) != 1:
            issues.append({"code": "invalid_status_subject_edge", "node_id": transition_id, "subjects": subject_ids})
            continue
        subject_id = subject_ids[0]
        subject = nodes.get(subject_id)
        if subject is None:
            issues.append({"code": "missing_status_subject", "node_id": transition_id, "subject_id": subject_id})
            continue
        subject_hash = payload.get("subject_hash")
        if not isinstance(subject_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", subject_hash):
            issues.append({"code": "invalid_subject_hash", "node_id": transition_id})
        elif subject_hash != semantic_hash(subject):
            issues.append({"code": "status_subject_hash_mismatch", "node_id": transition_id, "subject_id": subject_id})
        linked = any(
            edge.get("from") == subject_id
            and edge.get("to") == transition_id
            and edge.get("rel") == STATUS_TRANSITION_REL
            for edge in edges
        )
        if not linked:
            issues.append({"code": "missing_status_transition_edge", "node_id": transition_id, "subject_id": subject_id})

    for node_id, node in nodes.items():
        transitions = status_transition_nodes(graph, node_id)
        if transitions:
            derived = status_transition_payload(transitions[-1]).get("to_status")
            cached = node.get("status") or "unclassified"
            if derived != cached:
                issues.append({"code": "status_cache_mismatch", "node_id": node_id, "cached": cached, "derived": derived})

    return {"valid": not issues, "issues": issues, "checked_nodes": len(nodes)}
