"""Hard-stop immutability rules for committed Grapher records."""

from __future__ import annotations

import json
from collections import Counter
from typing import Any


# These fields are still operational caches/metadata in the hard-stop beta.
# Their eventual event-sourced representation is deliberately deferred.
_COMMITTED_MUTABLE_FIELDS = frozenset(
    {
        "status",
        "workflow_state",
        "verification",
        "stage",
        "updated_at",
        "finalized_at",
        "integrity",
    }
)
_DRAFT_IDENTITY_FIELDS = frozenset({"id", "type", "path", "created_at"})


def is_pending_ingest_draft(node: dict[str, Any] | None) -> bool:
    """Return True only for the narrow editable ingest-stub exception."""
    if not node or node.get("finalized_at"):
        return False
    meta = node.get("meta") or {}
    if meta.get("source") != "ingest":
        return False
    if str(node.get("status") or "unclassified") != "unclassified":
        return False
    return bool(meta.get("status") == "pending" or not str(node.get("content") or "").strip())


def changed_fields(
    existing: dict[str, Any],
    candidate: dict[str, Any],
    *,
    ignore: frozenset[str] = frozenset(),
) -> list[str]:
    return sorted(
        field
        for field in (set(existing) | set(candidate))
        if field not in ignore and existing.get(field) != candidate.get(field)
    )


def assert_draft_identity_unchanged(
    existing: dict[str, Any],
    candidate: dict[str, Any],
    *,
    node_id: str | None = None,
) -> None:
    """Pending ingest drafts may be enriched, but never retargeted or retyped."""
    changed = [
        field
        for field in _DRAFT_IDENTITY_FIELDS
        if existing.get(field) != candidate.get(field)
    ]
    if changed:
        raise ValueError(
            f"pending ingest draft {node_id or existing.get('id')!r} cannot change identity fields: "
            + ", ".join(sorted(changed))
        )


def assert_committed_record_unchanged(
    existing: dict[str, Any],
    candidate: dict[str, Any],
    *,
    node_id: str | None = None,
) -> None:
    """Reject in-place rewrites of assertion-bearing committed record fields."""
    changed = changed_fields(existing, candidate, ignore=_COMMITTED_MUTABLE_FIELDS)

    # Sealing may be added, but an existing seal/finalization marker is itself immutable.
    if existing.get("finalized_at") and existing.get("finalized_at") != candidate.get("finalized_at"):
        changed.append("finalized_at")
    if existing.get("integrity") and existing.get("integrity") != candidate.get("integrity"):
        changed.append("integrity")

    if changed:
        changed = sorted(set(changed))
        raise ValueError(
            f"committed record {node_id or existing.get('id')!r} is immutable; changed fields: "
            + ", ".join(changed)
            + ". Create a new correcting record and relate or supersede the original."
        )


def _edge_key(edge: dict[str, Any]) -> str:
    return json.dumps(edge, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def enforce_hard_stop(before: dict[str, Any] | None, after: dict[str, Any]) -> None:
    """Enforce append-oriented graph mutations before canonical persistence.

    Existing committed nodes may only change operational cache fields. Pending ingest
    drafts may be enriched but keep stable identity. Existing edges may not disappear
    or be rewritten; new nodes and new edges may only be appended.
    """
    if before is None:
        return

    old_nodes = before.get("nodes") or {}
    new_nodes = after.get("nodes") or {}
    for node_id, existing in old_nodes.items():
        candidate = new_nodes.get(node_id)
        if candidate is None:
            if is_pending_ingest_draft(existing):
                continue
            raise ValueError(
                f"committed record {node_id!r} cannot be removed. "
                "Create a correcting record and preserve the original."
            )
        if is_pending_ingest_draft(existing):
            assert_draft_identity_unchanged(existing, candidate, node_id=node_id)
        else:
            assert_committed_record_unchanged(existing, candidate, node_id=node_id)

    old_edges = Counter(_edge_key(edge) for edge in (before.get("edges") or []))
    new_edges = Counter(_edge_key(edge) for edge in (after.get("edges") or []))
    missing = old_edges - new_edges
    if missing:
        raise ValueError(
            "existing graph relations are append-only in hard-stop mode; "
            "an existing edge was removed or rewritten"
        )
