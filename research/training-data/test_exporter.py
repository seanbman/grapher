import importlib.util
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("exporter", Path(__file__).with_name("exporter.py"))
exporter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(exporter)


def node(i, t, semantic=None, **kw):
    value = {"id":i,"type":t,"title":i,"status":"current","verification":"unverified","workflow_state":"not_applicable","semantic":semantic or {},"content":"","evidence":[],"source_refs":[],"provenance":{},"scope":{}}
    value.update(kw); return value


class ExporterTests(unittest.TestCase):
    def test_verified_outcome_uses_only_its_antecedent(self):
        graph={"nodes":{"d":node("d","decision",{"decision":"Do X","rationale":"Because Y"}),"r":node("r","result",{"result":"X worked","evidence":"test"},verification="verified",evidence=[{"ref":"pytest"}])},"edges":[{"from":"r","to":"d","rel":"derived_from"}]}
        out=exporter.export_snapshot(graph,{"graph_hash":"a"*64,"publication_id":"abc","version":1},created_at="2026-09-05T00:00:00+00:00")
        self.assertEqual(out["metrics"]["eligible_count"],1)
        self.assertEqual(out["examples"][0]["target"]["records"][0]["id"],"r")
        self.assertEqual(out["examples"][0]["input"]["records"][0]["id"],"d")
        self.assertEqual(out["metrics"]["rejection_reasons"]["no_grounded_predecessor"],1)

    def test_ungrounded_and_unverified_outcome_rejected(self):
        graph={"nodes":{"r":node("r","result",{"result":"Maybe","evidence":"none"})},"edges":[]}
        out=exporter.export_snapshot(graph,{"graph_hash":"b"*64,"publication_id":"def","version":1},created_at="2026-09-05T00:00:00+00:00")
        self.assertEqual(out["metrics"]["eligible_count"],0)
        self.assertEqual(out["metrics"]["rejection_reasons"]["no_grounded_predecessor"],1)
        self.assertEqual(out["metrics"]["rejection_reasons"]["outcome_without_evidence"],1)


if __name__ == "__main__": unittest.main()
