import importlib.util
import unittest
from copy import deepcopy
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("enrichment", Path(__file__).with_name("enrichment.py"))
enrichment = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(enrichment)


def graph_with(node):
    return {"nodes": {node["id"]: node}, "edges": []}


class EnrichmentTests(unittest.TestCase):
    def test_preview_leaves_candidate_values_empty(self):
        graph = graph_with({"id":"f1","type":"finding","title":"Observed issue","content":"Playback overlaps on loop restart."})
        original = deepcopy(graph)
        out = enrichment.preview(graph)
        self.assertEqual(out["review_count"], 1)
        self.assertEqual(graph, original)
        item = out["records"][0]
        self.assertIn("failure", [c["type"] for c in item["candidates"]])
        self.assertTrue(all(c["values"] == {} for c in item["candidates"]))

    def test_compose_requires_allowed_type_and_complete_explicit_fields(self):
        graph = graph_with({"id":"i1","type":"instruction","title":"Keep audio stable","content":"Do not let notes leak into the next cycle."})
        with self.assertRaises(ValueError):
            enrichment.compose_successor(graph,"i1","decision",{"decision":"x","rationale":"y"},actor_id="agent",actor_kind="agent",reason="review")
        with self.assertRaises(ValueError):
            enrichment.compose_successor(graph,"i1","constraint",{"constraint":"Prevent overlap"},actor_id="agent",actor_kind="agent",reason="review")

    def test_compose_validated_successor_preserves_source(self):
        graph = graph_with({"id":"f1","type":"finding","title":"Overlap observed","content":"A held pad can overlap the next pattern iteration.","scope":{"project_id":"pocket-synth"},"stage":"developing"})
        original = deepcopy(graph)
        out = enrichment.compose_successor(
            graph,"f1","failure",
            {"failure":"Pattern iteration allows a held pad to overlap the next cycle","observed_behavior":"Audio from the prior iteration continues after the next iteration starts"},
            actor_id="reviewer",actor_kind="human",reason="manual semantic enrichment",
            successor_id="failure-overlap-enriched",created_at="2026-09-05T00:00:00+00:00",
        )
        self.assertEqual(graph, original)
        self.assertEqual(out["source"]["id"], "f1")
        self.assertEqual(out["successor"]["type"], "failure")
        self.assertEqual(out["successor"]["status"], "proposed")
        self.assertEqual(out["relation"]["rel"], "derived_from")
        self.assertEqual(out["relation"]["to"], "f1")
        self.assertTrue(out["review"]["validated"])
        self.assertFalse(out["review"]["source_mutated"])


if __name__ == "__main__":
    unittest.main()
