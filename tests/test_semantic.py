from __future__ import annotations

import json

import pytest

from grapher.graph import add_node
from grapher.model import empty_graph
from grapher.registry import BUILTIN_NODE_TYPES
from grapher.semantic import (
    CANONICAL_ENTRY_TYPES,
    SEMANTIC_ENTRY_CONTRACTS,
    semantic_contract,
)


VALID_PAYLOADS = {
    "observation": {"observation": "Loop audio overlaps at restart", "source": "browser playback test"},
    "problem": {"problem": "Loop audio overlaps at restart", "impact": "Pattern playback is audibly incorrect"},
    "question": {"question": "Which voice survives restart?", "importance": "It identifies the cleanup failure"},
    "hypothesis": {"hypothesis": "A stale voice survives", "basis": "Overlap begins exactly at restart", "validation_condition": "Trace active voices across restart"},
    "requirement": {"requirement": "Recorded piano can become a track", "acceptance_condition": "Recording can be assigned to a lane and reloaded"},
    "constraint": {"constraint": "Finalized history is immutable", "reason": "Historical provenance must remain trustworthy"},
    "proposal": {"proposal": "Stop voices before restart", "rationale": "It prevents prior-iteration overlap"},
    "decision": {"decision": "Use typed semantic entries", "rationale": "Normalization should happen at write time"},
    "task": {"action": "Trace active voices at restart", "expected_outcome": "Identify the surviving voice"},
    "implementation": {"change": "Added voice cleanup before restart", "component": "pattern scheduler"},
    "test": {"test": "Loop pattern 100 times", "method": "Automated browser playback", "outcome": "pass"},
    "result": {"result": "No voices survived restart", "evidence": "100-loop playback trace"},
    "failure": {"failure": "Pad audio leaks into next iteration", "observed_behavior": "Previous pad continues after restart"},
    "lesson": {"lesson": "Loop boundaries must explicitly terminate owned voices", "derived_from": ["failure-1", "test-1"]},
}


def test_canonical_entry_types_are_builtin():
    assert CANONICAL_ENTRY_TYPES <= BUILTIN_NODE_TYPES


def test_every_semantic_type_has_a_contract():
    assert set(SEMANTIC_ENTRY_CONTRACTS) == set(VALID_PAYLOADS)


@pytest.mark.parametrize("node_type,payload", VALID_PAYLOADS.items())
def test_semantic_types_store_normalized_payload(node_type: str, payload: dict):
    graph = empty_graph()
    node = add_node(
        graph,
        id=f"{node_type}-1",
        type=node_type,
        title=f"{node_type} example",
        content=json.dumps(payload),
    )
    assert node["semantic"] == payload


def test_semantic_contract_is_machine_readable_and_strict():
    contract = semantic_contract("decision")
    assert contract == {
        "type": "decision",
        "required_fields": ["decision", "rationale"],
        "allowed_fields": ["decision", "rationale"],
        "field_types": {"decision": "string", "rationale": "string"},
        "additional_fields": False,
        "constraints": {},
    }


def test_semantic_content_rejects_free_form_text():
    graph = empty_graph()
    with pytest.raises(ValueError, match="requires --content to be a JSON object"):
        add_node(
            graph,
            id="decision-1",
            type="decision",
            title="Choose schema",
            content="Use typed semantic entries because normalization matters.",
        )


def test_semantic_content_rejects_missing_required_fields():
    graph = empty_graph()
    with pytest.raises(ValueError, match="rationale"):
        add_node(
            graph,
            id="decision-1",
            type="decision",
            title="Choose schema",
            content=json.dumps({"decision": "Use typed semantic entries"}),
        )


def test_semantic_content_rejects_unexpected_fields():
    graph = empty_graph()
    with pytest.raises(ValueError, match="does not allow field.*notes"):
        add_node(
            graph,
            id="decision-1",
            type="decision",
            title="Choose schema",
            content=json.dumps(
                {
                    "decision": "Use typed semantic entries",
                    "rationale": "Normalize at write time",
                    "notes": "free-form spillover",
                }
            ),
        )


def test_semantic_content_rejects_wrong_field_type():
    graph = empty_graph()
    with pytest.raises(ValueError, match="field 'rationale' must be a string"):
        add_node(
            graph,
            id="decision-1",
            type="decision",
            title="Choose schema",
            content=json.dumps(
                {
                    "decision": "Use typed semantic entries",
                    "rationale": ["normalize", "validate"],
                }
            ),
        )


def test_semantic_content_rejects_filler():
    graph = empty_graph()
    with pytest.raises(ValueError, match="rationale"):
        add_node(
            graph,
            id="decision-1",
            type="decision",
            title="Choose schema",
            content=json.dumps({"decision": "Use typed semantic entries", "rationale": "TBD"}),
        )


def test_working_task_stub_remains_allowed():
    graph = empty_graph()
    node = add_node(graph, id="task-1", type="task", title="Trace loop voices")
    assert "semantic" not in node


def test_durable_semantic_stub_is_rejected():
    graph = empty_graph()
    with pytest.raises(ValueError, match="durable semantic node"):
        add_node(
            graph,
            id="task-1",
            type="task",
            title="Trace loop voices",
            status="current",
        )


def test_test_outcome_is_constrained():
    graph = empty_graph()
    payload = dict(VALID_PAYLOADS["test"], outcome="maybe")
    with pytest.raises(ValueError, match="outcome"):
        add_node(
            graph,
            id="test-1",
            type="test",
            title="Loop playback",
            content=json.dumps(payload),
        )


def test_lesson_derived_from_requires_substantive_string_ids():
    graph = empty_graph()
    payload = dict(VALID_PAYLOADS["lesson"], derived_from=["failure-1", "TBD"])
    with pytest.raises(ValueError, match="derived_from"):
        add_node(
            graph,
            id="lesson-1",
            type="lesson",
            title="Loop ownership",
            content=json.dumps(payload),
        )


def test_unchanged_legacy_semantic_content_can_be_operationally_updated():
    graph = empty_graph()
    graph["nodes"]["legacy"] = {
        "id": "legacy",
        "type": "decision",
        "title": "Legacy decision",
        "content": "old free-form decision",
        "status": "unclassified",
        "workflow_state": "not_applicable",
        "verification": "unverified",
        "evidence": [],
        "source_refs": [],
        "owners": [],
        "meta": {},
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
    }
    node = add_node(
        graph,
        id="legacy",
        type="decision",
        title="Legacy decision",
        content="old free-form decision",
        workflow_state="active",
    )
    assert node["content"] == "old free-form decision"
    assert "semantic" not in node


def test_rewriting_legacy_semantic_content_requires_normalization():
    graph = empty_graph()
    graph["nodes"]["legacy"] = {
        "id": "legacy",
        "type": "decision",
        "title": "Legacy decision",
        "content": "old free-form decision",
        "meta": {},
    }
    with pytest.raises(ValueError, match="JSON object"):
        add_node(
            graph,
            id="legacy",
            type="decision",
            title="Legacy decision",
            content="new free-form decision",
        )
