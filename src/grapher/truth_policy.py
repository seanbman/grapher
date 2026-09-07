"""Truth-status admission policy for newly authored graph nodes."""

from __future__ import annotations

from typing import Any

EXPLICIT_STATUS_CONFIG_KEY = "require_explicit_status"
LEGACY_ALLOWLIST_CONFIG_KEY = "truth_status_legacy_allowlist"
TRUTH_REVIEW_META_KEY = "truth_review"


def is_truth_review_node(node: dict[str, Any]) -> bool:
    """Return True when an unclassified node is deliberately awaiting review."""
    meta = node.get("meta") or {}
    if meta.get(TRUTH_REVIEW_META_KEY) is True:
        return True
    return bool(
        meta.get("source") == "ingest"
        and (meta.get("status") == "pending" or not (node.get("content") or "").strip())
    )


def unclassified_authored_node_ids(
    graph: dict[str, Any],
    *,
    legacy_allowlist: set[str] | frozenset[str] | None = None,
) -> list[str]:
    """List authored nodes still using the unclassified truth status."""
    allowed = set(legacy_allowlist or ())
    bad: list[str] = []
    for node_id, node in (graph.get("nodes") or {}).items():
        if node_id in allowed:
            continue
        if str(node.get("status") or "unclassified") != "unclassified":
            continue
        if is_truth_review_node(node):
            continue
        bad.append(str(node_id))
    return sorted(bad)


def newly_unclassified_authored_node_ids(
    before: dict[str, Any] | None,
    after: dict[str, Any],
) -> list[str]:
    """Return new authored node ids that were admitted without classification."""
    old_ids = set(((before or {}).get("nodes") or {}).keys())
    created = {
        node_id: node
        for node_id, node in (after.get("nodes") or {}).items()
        if node_id not in old_ids
    }
    return unclassified_authored_node_ids({"nodes": created})


def enforce_new_node_truth_status(
    before: dict[str, Any] | None,
    after: dict[str, Any],
    *,
    enabled: bool,
) -> None:
    """Reject newly authored semantic nodes that omit an explicit truth status."""
    if not enabled:
        return
    bad = newly_unclassified_authored_node_ids(before, after)
    if not bad:
        return
    joined = ", ".join(bad)
    raise ValueError(
        "explicit truth status required for new authored node(s): "
        f"{joined}. Supply a classified status; unclassified is reserved for "
        "raw ingest or nodes explicitly marked meta.truth_review=true."
    )
