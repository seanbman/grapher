import importlib.util
import unittest
from copy import deepcopy
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("legacy_normalization", Path(__file__).with_name("legacy_normalization.py"))
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


class LegacyNormalizationTests(unittest.TestCase):
    def test_three_dispositions_are_conservative(self):
        graph={"nodes":{
            "canonical":{"id":"canonical","type":"decision","semantic":{"decision":"Use X","rationale":"Because Y"}},
            "legacy-decision":{"id":"legacy-decision","type":"decision","content":"Use X"},
            "finding":{"id":"finding","type":"finding","content":"Observed X"},
            "image":{"id":"image","type":"image","content":"screen"},
        }}
        before=deepcopy(graph)
        out=mod.preview(graph,"git:test")
        rows={r["id"]:r for r in out["records"]}
        self.assertEqual(rows["canonical"]["disposition"],"mechanically_mappable")
        self.assertEqual(rows["legacy-decision"]["disposition"],"enrichment_required")
        self.assertEqual(rows["finding"]["disposition"],"enrichment_required")
        self.assertEqual(rows["image"]["disposition"],"context_only")
        self.assertEqual(graph,before)

    def test_finding_is_not_auto_retyped(self):
        row=mod.classify({"type":"finding","content":"A test failed"})
        self.assertEqual(row["disposition"],"enrichment_required")
        self.assertGreater(len(row["candidate_types"]),1)


if __name__ == "__main__": unittest.main()
