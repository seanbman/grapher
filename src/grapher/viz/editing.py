"""Review-first, approval-gated mutation helpers for Dash."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from grapher.curate import set_status
from grapher.graph import get_node
from grapher.registry import TRUTH_STATUSES
from grapher.store import load_graph, save_graph_mutation


class EditApprovalError(ValueError):
    """Raised when a proposed dashboard edit is not safely approved."""


def _proposal_id(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "dash-edit-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def preview_status_edit(
    graph: dict[str, Any],
    *,
    node_id: str,
    status: str,
    reason: str,
) -> dict[str, Any]:
    """Create a stable, non-mutating status-edit proposal for explicit review."""
    if status not in TRUTH_STATUSES:
        raise EditApprovalError(f"unknown status {status!r}")
    reason = reason.strip()
    if not reason:
        raise EditApprovalError("dashboard status edits require a reason")
    node = get_node(graph, node_id)
    payload = {
        "kind": "status_edit",
        "node_id": node_id,
        "title": node.get("title"),
        "before": node.get("status") or "unclassified",
        "after": status,
        "reason": reason,
    }
    return {**payload, "proposal_id": _proposal_id(payload), "approved": False}


def apply_approved_status_edit(
    graph_path: Path,
    proposal: dict[str, Any],
    *,
    approval_id: str,
    actor_id: str,
) -> dict[str, Any]:
    """Apply exactly the reviewed proposal after explicit matching approval."""
    if not actor_id.strip():
        raise EditApprovalError("approved dashboard edits require actor attribution")
    expected_payload = {
        key: proposal.get(key)
        for key in ("kind", "node_id", "title", "before", "after", "reason")
    }
    expected_id = _proposal_id(expected_payload)
    if proposal.get("proposal_id") != expected_id or approval_id != expected_id:
        raise EditApprovalError("approval does not match the reviewed proposal")
    if proposal.get("kind") != "status_edit":
        raise EditApprovalError("unsupported dashboard edit kind")

    before = load_graph(graph_path, normalize=False)
    graph = load_graph(graph_path)
    node = get_node(graph, str(proposal["node_id"]))
    current = node.get("status") or "unclassified"
    if current != proposal.get("before"):
        raise EditApprovalError(
            f"node status changed since preview: expected {proposal.get('before')!r}, found {current!r}"
        )

    result = set_status(graph, str(proposal["node_id"]), str(proposal["after"]))
    entry = save_graph_mutation(
        graph_path,
        graph,
        action="dashboard_status_edit_approved",
        target=str(proposal["node_id"]),
        before=before,
        source="dash",
        actor={"kind": "human", "id": actor_id.strip(), "role": "dashboard_editor"},
        reason=str(proposal["reason"]),
        phase="executed",
        context={"approval_id": approval_id, "proposal": expected_payload},
    )
    return {
        "proposal_id": approval_id,
        "applied": True,
        "edit": result,
        "history_operation_id": entry.get("operation_id"),
    }
