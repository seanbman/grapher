"""Canonical semantic entry contracts and write-time validation.

Semantic entries may exist as empty working stubs, but once semantic content is
written it must be a JSON object satisfying the entry type's contract.
Durable/current/verified/finalized semantic entries may not remain empty.
"""

from __future__ import annotations

import json
import re
from typing import Any


SEMANTIC_ENTRY_CONTRACTS: dict[str, dict[str, Any]] = {
    "observation": {"required": {"observation": "string", "source": "string"}},
    "problem": {"required": {"problem": "string", "impact": "string"}},
    "question": {"required": {"question": "string", "importance": "string"}},
    "hypothesis": {
        "required": {
            "hypothesis": "string",
            "basis": "string",
            "validation_condition": "string",
        }
    },
    "requirement": {
        "required": {"requirement": "string", "acceptance_condition": "string"}
    },
    "constraint": {"required": {"constraint": "string", "reason": "string"}},
    "proposal": {"required": {"proposal": "string", "rationale": "string"}},
    "decision": {"required": {"decision": "string", "rationale": "string"}},
    "task": {"required": {"action": "string", "expected_outcome": "string"}},
    "implementation": {"required": {"change": "string", "component": "string"}},
    "test": {
        "required": {"test": "string", "method": "string", "outcome": "string"}
    },
    "result": {"required": {"result": "string", "evidence": "string"}},
    "failure": {
        "required": {"failure": "string", "observed_behavior": "string"}
    },
    "lesson": {"required": {"lesson": "string", "derived_from": "string_list"}},
    "status_transition": {
        "required": {
            "subject_hash": "string",
            "from_status": "string",
            "to_status": "string",
            "reason": "string",
            "operation_id": "string",
        }
    },
}

# Backward-compatible compact view used by callers and documentation helpers.
SEMANTIC_ENTRY_SCHEMAS: dict[str, tuple[str, ...]] = {
    node_type: tuple(contract["required"])
    for node_type, contract in SEMANTIC_ENTRY_CONTRACTS.items()
}

CANONICAL_ENTRY_TYPES: frozenset[str] = frozenset(SEMANTIC_ENTRY_CONTRACTS)
DURABLE_STATUSES: frozenset[str] = frozenset({"current", "canonical_spec"})
DURABLE_VERIFICATION: frozenset[str] = frozenset({"partially_verified", "verified"})
TEST_OUTCOMES: frozenset[str] = frozenset({"pass", "fail", "partial", "inconclusive"})

_FILLER = frozenset(
    {
        "todo",
        "tbd",
        "n/a",
        "na",
        "none",
        "unknown",
        "fix later",
        "investigate",
        "investigate later",
        "needs work",
        "need to investigate",
        "something might be wrong",
        "looks good",
        "improve this",
    }
)


def _normalized_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower()).rstrip(".!?")


def _has_substance(value: Any) -> bool:
    if isinstance(value, str):
        text = _normalized_text(value)
        return bool(text) and text not in _FILLER
    if isinstance(value, list):
        return bool(value) and all(_has_substance(item) for item in value)
    if isinstance(value, dict):
        return bool(value)
    return value is not None


def _validate_field_type(node_type: str, field: str, value: Any, field_type: str) -> None:
    if field_type == "string":
        if not isinstance(value, str):
            raise ValueError(
                f"semantic node type {node_type!r} field {field!r} must be a string"
            )
        return
    if field_type == "string_list":
        if not isinstance(value, list) or not value or not all(
            isinstance(item, str) and _has_substance(item) for item in value
        ):
            raise ValueError(
                f"semantic node type {node_type!r} field {field!r} must be a non-empty list of substantive strings"
            )
        return
    raise ValueError(
        f"semantic node type {node_type!r} has unsupported schema field type {field_type!r}"
    )


def semantic_contract(node_type: str) -> dict[str, Any]:
    """Return a stable, JSON-ready description of one semantic entry contract."""
    contract = SEMANTIC_ENTRY_CONTRACTS.get(node_type)
    if contract is None:
        raise ValueError(f"unknown semantic node type {node_type!r}")
    required = dict(contract["required"])
    constraints: dict[str, Any] = {}
    if node_type == "test":
        constraints["outcome"] = sorted(TEST_OUTCOMES)
    if node_type == "status_transition":
        from grapher.registry import TRUTH_STATUSES

        constraints["from_status"] = sorted(TRUTH_STATUSES)
        constraints["to_status"] = sorted(TRUTH_STATUSES)
        constraints["subject_hash"] = "64 lowercase hexadecimal SHA-256 characters"
    return {
        "type": node_type,
        "required_fields": list(required),
        "allowed_fields": list(required),
        "field_types": required,
        "additional_fields": False,
        "constraints": constraints,
    }


def semantic_contracts() -> dict[str, dict[str, Any]]:
    """Return all canonical semantic entry contracts for agent/tool introspection."""
    return {
        node_type: semantic_contract(node_type)
        for node_type in sorted(CANONICAL_ENTRY_TYPES)
    }


def requires_semantic_content(node: dict[str, Any]) -> bool:
    """Whether an otherwise-empty semantic node has crossed a durable boundary."""
    return bool(
        node.get("finalized_at")
        or node.get("status") in DURABLE_STATUSES
        or node.get("verification") in DURABLE_VERIFICATION
    )


def parse_semantic_content(node_type: str, content: str) -> dict[str, Any]:
    """Parse and validate canonical semantic JSON content."""
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"semantic node type {node_type!r} requires --content to be a JSON object; "
            f"invalid JSON: {exc.msg}"
        ) from exc

    if not isinstance(payload, dict):
        raise ValueError(f"semantic node type {node_type!r} requires JSON object content")

    contract = SEMANTIC_ENTRY_CONTRACTS[node_type]
    required: dict[str, str] = contract["required"]
    missing = [
        field
        for field in required
        if field not in payload or not _has_substance(payload[field])
    ]
    if missing:
        raise ValueError(
            f"semantic node type {node_type!r} requires substantive field(s): "
            + ", ".join(missing)
        )

    unexpected = sorted(set(payload) - set(required))
    if unexpected:
        raise ValueError(
            f"semantic node type {node_type!r} does not allow field(s): "
            + ", ".join(unexpected)
            + "; allowed fields: "
            + ", ".join(required)
        )

    for field, field_type in required.items():
        _validate_field_type(node_type, field, payload[field], field_type)

    if node_type == "test" and payload["outcome"] not in TEST_OUTCOMES:
        raise ValueError(
            f"semantic test outcome must be one of {sorted(TEST_OUTCOMES)}"
        )

    if node_type == "status_transition":
        from grapher.registry import TRUTH_STATUSES

        for field in ("from_status", "to_status"):
            if payload[field] not in TRUTH_STATUSES:
                raise ValueError(
                    f"semantic status transition {field} must be one of {sorted(TRUTH_STATUSES)}"
                )
        if not re.fullmatch(r"[0-9a-f]{64}", payload["subject_hash"]):
            raise ValueError(
                "semantic status transition subject_hash must be a lowercase SHA-256 hex digest"
            )

    return payload


def semantic_payload_for_node(node: dict[str, Any]) -> dict[str, Any] | None:
    """Validate a node and return its normalized semantic payload when applicable."""
    node_type = str(node.get("type") or "")
    if node_type not in CANONICAL_ENTRY_TYPES:
        return None

    content = str(node.get("content") or "").strip()
    if not content:
        if requires_semantic_content(node):
            required = ", ".join(SEMANTIC_ENTRY_SCHEMAS[node_type])
            raise ValueError(
                f"durable semantic node type {node_type!r} requires structured content "
                f"with fields: {required}"
            )
        return None

    return parse_semantic_content(node_type, content)
