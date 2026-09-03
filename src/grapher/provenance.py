"""Structured, append-only provenance for canonical graph mutations."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from grapher.model import now_iso

ACTOR_KINDS = frozenset({"human", "agent", "system_tool", "migration_import"})
TRANSITION_PHASES = frozenset({"proposed", "executed", "observed", "verified", "canonical"})


def actor_record(source: str, actor: dict[str, Any] | None = None) -> dict[str, Any]:
    """Normalize a model-agnostic actor/source record."""
    result = dict(actor or {})
    kind = result.get("kind")
    if not kind:
        lowered = source.lower()
        if any(token in lowered for token in ("migrat", "import", "transfer", "unpack")):
            kind = "migration_import"
        elif result.get("id") or result.get("actor_id"):
            kind = "agent"
        else:
            kind = "system_tool"
    if kind not in ACTOR_KINDS:
        raise ValueError(f"unknown actor kind {kind!r}; choose from {sorted(ACTOR_KINDS)}")
    result["kind"] = kind
    result.setdefault("source", source)
    return {key: value for key, value in result.items() if value is not None}


def _event_type(field: str, previous: Any, resulting: Any) -> str:
    return {
        "workflow_state": "workflow_state_changed",
        "verification": "verification_state_changed",
        "status": "node_status_changed",
        "stage": "lifecycle_stage_changed",
    }.get(field) or (
        "evidence_attached" if field == "evidence" and not previous and resulting else
        "evidence_invalidated" if field == "evidence" and previous and not resulting else
        "evidence_changed" if field == "evidence" else
        "canonical_state_finalized" if field == "finalized_at" and resulting else
        "canonical_state_reopened" if field == "finalized_at" else
        "node_field_changed"
    )


def transition_records(
    before: dict[str, Any] | None, after: dict[str, Any], *, actor: dict[str, Any],
    operation_id: str, phase: str, reason: str | None = None,
    evidence_refs: list[str] | None = None, decision_ids: list[str] | None = None,
    requirement_ids: list[str] | None = None, supersedes: list[str] | None = None,
    overrides: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Diff two canonical graphs into immutable, field-level transition records."""
    timestamp = now_iso()
    old_nodes, new_nodes = (before or {}).get("nodes") or {}, after.get("nodes") or {}
    common = {"timestamp": timestamp, "actor": actor, "phase": phase, "operation_id": operation_id}
    optional = {
        "reason": reason, "evidence_refs": evidence_refs or None,
        "related_decision_ids": decision_ids or None,
        "related_requirement_ids": requirement_ids or None,
        "supersedes_transition_ids": supersedes or None,
        "overrides_transition_ids": overrides or None,
    }
    records: list[dict[str, Any]] = []

    def record(**values: Any) -> None:
        records.append({"id": f"transition-{uuid.uuid4().hex}", **common,
                        **{k: v for k, v in optional.items() if v is not None}, **values})

    for node_id in sorted(set(old_nodes) | set(new_nodes)):
        previous, resulting = old_nodes.get(node_id), new_nodes.get(node_id)
        if previous is None:
            record(entity_id=node_id, entity_kind="node", event_type="node_created",
                   previous_value=None, resulting_value=resulting)
            continue
        if resulting is None:
            record(entity_id=node_id, entity_kind="node", event_type="node_removed",
                   previous_value=previous, resulting_value=None)
            continue
        for field in sorted(set(previous) | set(resulting)):
            if field == "updated_at" or previous.get(field) == resulting.get(field):
                continue
            record(entity_id=node_id, entity_kind="node",
                   event_type=_event_type(field, previous.get(field), resulting.get(field)),
                   field=field, previous_value=previous.get(field), resulting_value=resulting.get(field))

    def edge_key(edge: dict[str, Any]) -> str:
        return json.dumps({k: v for k, v in edge.items() if k != "created_at"},
                          sort_keys=True, ensure_ascii=False, separators=(",", ":"))

    old_edges = {edge_key(e): e for e in (before or {}).get("edges") or []}
    new_edges = {edge_key(e): e for e in after.get("edges") or []}
    for key in sorted(set(old_edges) | set(new_edges)):
        previous, resulting = old_edges.get(key), new_edges.get(key)
        if previous is not None and resulting is not None:
            continue
        edge, added = resulting or previous or {}, resulting is not None
        relation = edge.get("rel")
        if relation == "depends_on":
            event_type = "dependency_added" if added else "dependency_removed"
        elif relation == "blocks":
            event_type = "blocker_appeared" if added else "blocker_resolved"
        elif relation in {"verified_by", "evidenced_by"}:
            event_type = "evidence_attached" if added else "evidence_invalidated"
        elif relation == "supersedes":
            event_type = "supersession_recorded" if added else "supersession_removed"
        else:
            event_type = "relation_added" if added else "relation_removed"
        record(entity_id=f"{edge.get('from')}:{relation}:{edge.get('to')}", entity_kind="edge",
               affected_node_ids=[edge.get("from"), edge.get("to")], event_type=event_type,
               previous_value=previous, resulting_value=resulting)
    return records


def make_history_entry(
    before: dict[str, Any] | None, after: dict[str, Any], *, action: str,
    target: str | None, source: str, result: str, before_hash: str | None,
    after_hash: str, actor: dict[str, Any] | None = None, reason: str | None = None,
    evidence_refs: list[str] | None = None, decision_ids: list[str] | None = None,
    requirement_ids: list[str] | None = None, supersedes: list[str] | None = None,
    overrides: list[str] | None = None, operation_id: str | None = None,
    phase: str = "executed", context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if phase not in TRANSITION_PHASES:
        raise ValueError(f"unknown transition phase {phase!r}; choose from {sorted(TRANSITION_PHASES)}")
    operation_id = operation_id or f"operation-{uuid.uuid4().hex}"
    actor = actor_record(source, actor)
    entry = {
        "id": f"event-{uuid.uuid4().hex}", "action": action, "recorded_at": now_iso(),
        "target": target, "source": source, "actor": actor, "phase": phase,
        "operation_id": operation_id, "operation_result": result, "result": result,
        "before_hash": before_hash, "after_hash": after_hash,
        "transitions": transition_records(
            before, after, actor=actor, operation_id=operation_id, phase=phase,
            reason=reason, evidence_refs=evidence_refs, decision_ids=decision_ids,
            requirement_ids=requirement_ids, supersedes=supersedes, overrides=overrides,
        ),
    }
    if context:
        entry["context"] = context
    return entry


def load_history(
    graph_path: Path, *, entity_id: str | None = None,
    operation_id: str | None = None, event_type: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Read structured history while tolerating legacy hash-only entries."""
    path = graph_path.parent / "history.jsonl"
    if not path.is_file():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        transitions = entry.get("transitions") or []
        if entity_id and not any(t.get("entity_id") == entity_id or entity_id in (t.get("affected_node_ids") or []) for t in transitions):
            continue
        if operation_id and entry.get("operation_id") != operation_id:
            continue
        if event_type and not any(t.get("event_type") == event_type for t in transitions):
            continue
        entries.append(entry)
    return [] if limit is not None and limit <= 0 else (entries[-limit:] if limit is not None else entries)


def validate_history(graph_path: Path) -> dict[str, Any]:
    """Validate structured records while accepting pre-addendum legacy entries."""
    path = graph_path.parent / "history.jsonl"
    if not path.is_file():
        return {"valid": True, "entries": 0, "transitions": 0, "legacy_entries": 0, "issues": []}
    issues: list[dict[str, Any]] = []
    seen: set[str] = set()
    entries = transitions = legacy = 0
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        entries += 1
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as exc:
            issues.append({"line": line_number, "code": "invalid_json", "message": str(exc)})
            continue
        records = entry.get("transitions")
        if records is None:
            legacy += 1
            continue
        if not isinstance(records, list):
            issues.append({"line": line_number, "code": "invalid_transitions"})
            continue
        for record in records:
            transitions += 1
            transition_id = record.get("id")
            if not transition_id:
                issues.append({"line": line_number, "code": "missing_transition_id"})
            elif transition_id in seen:
                issues.append({"line": line_number, "code": "duplicate_transition_id", "id": transition_id})
            seen.add(transition_id)
            if not record.get("entity_id") or not record.get("event_type") or not record.get("timestamp"):
                issues.append({"line": line_number, "code": "incomplete_transition", "id": transition_id})
            actor = record.get("actor") or {}
            if actor.get("kind") not in ACTOR_KINDS:
                issues.append({"line": line_number, "code": "invalid_actor_kind", "id": transition_id})
            if record.get("phase") not in TRANSITION_PHASES:
                issues.append({"line": line_number, "code": "invalid_transition_phase", "id": transition_id})
    return {"valid": not issues, "entries": entries, "transitions": transitions,
            "legacy_entries": legacy, "issues": issues}
