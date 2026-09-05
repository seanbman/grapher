"""Canonical semantic entry schemas and write-time validation.

Semantic entries may exist as empty working stubs, but once semantic content is
written it must be a JSON object satisfying the entry type's required fields.
Durable/current/verified/finalized semantic entries may not remain empty.
"""

from __future__ import annotations

import json
import re
from typing import Any


SEMANTIC_ENTRY_SCHEMAS: dict[str, tuple[str, ...]] = {
    "observation": ("observation", "source"),
    "problem": ("problem", "impact"),
    "question": ("question", "importance"),
    "hypothesis": ("hypothesis", "basis", "validation_condition"),
    "requirement": ("requirement", "acceptance_condition"),
    "constraint": ("constraint", "reason"),
    "proposal": ("proposal", "rationale"),
    "decision": ("decision", "rationale"),
    "task": ("action", "expected_outcome"),
    "implementation": ("change", "component"),
    "test": ("test", "method", "outcome"),
    "result": ("result", "evidence"),
    "failure": ("failure", "observed_behavior"),
    "lesson": ("lesson", "derived_from"),
}

CANONICAL_ENTRY_TYPES: frozenset[str] = frozenset(SEMANTIC_ENTRY_SCHEMAS)
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

    missing = [
        field
        for field in SEMANTIC_ENTRY_SCHEMAS[node_type]
        if field not in payload or not _has_substance(payload[field])
    ]
    if missing:
        raise ValueError(
            f"semantic node type {node_type!r} requires substantive field(s): "
            + ", ".join(missing)
        )

    if node_type == "test" and payload["outcome"] not in TEST_OUTCOMES:
        raise ValueError(
            f"semantic test outcome must be one of {sorted(TEST_OUTCOMES)}"
        )
    if node_type == "lesson" and not isinstance(payload["derived_from"], list):
        raise ValueError("semantic lesson derived_from must be a non-empty list")

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
