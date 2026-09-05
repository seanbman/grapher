#!/usr/bin/env python3
"""Read-only Grapher -> Derived Example v1 research exporter."""

from __future__ import annotations

import argparse, hashlib, json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EXPORTER_VERSION = "0.1.2"
POLICY_VERSION = "research-v1"
SEMANTIC_TYPES = {"observation","problem","question","hypothesis","requirement","constraint","proposal","decision","task","implementation","test","result","failure","lesson"}
EXCLUDED_TARGET_STATUSES = {"superseded","rejected","deprecated"}
# These relations point from a later/derived record to an antecedent/supporting record.
ANTECEDENT_RELS = {"derived_from","references","implements","satisfies","depends_on","requires","applies_to","verified_by","evidenced_by"}


def load(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sid(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()[:20]


def evidence_refs(node: dict[str, Any]) -> list[str]:
    return sorted({str(x["ref"]) for x in node.get("evidence", []) if isinstance(x, dict) and x.get("ref")})


def normalize(node: dict[str, Any]) -> dict[str, Any]:
    sem = node.get("semantic")
    content = {"kind":"semantic","value":sem} if isinstance(sem, dict) and sem else {"kind":"text","value":str(node.get("content") or "[missing content]")}
    p = node.get("provenance") or {}
    return {
        "id": str(node.get("id") or ""), "type": str(node.get("type") or "unknown"),
        "title": str(node.get("title") or node.get("id") or "untitled"),
        "status": str(node.get("status") or "unclassified"),
        "verification": str(node.get("verification") or "unverified"),
        "workflow_state": str(node.get("workflow_state") or "not_applicable"),
        "stage": node.get("stage"), "content": content,
        "provenance": {k:p.get(k) for k in ("actor_id","actor_kind","actor_role","source","integrity")},
        "source_refs": sorted(str(x) for x in node.get("source_refs", []) if x),
        "evidence_refs": evidence_refs(node),
    }


def kind_for(target_type: str, input_types: set[str]) -> str:
    if target_type == "decision": return "state_to_decision"
    if target_type in {"task","implementation"}: return "state_to_action"
    if target_type == "lesson" and "failure" in input_types: return "failure_to_lesson"
    if target_type in {"result","test","failure"} and input_types & {"decision","implementation","test"}: return "decision_to_outcome"
    if target_type in {"result","test","failure"}: return "verification_judgment"
    return "sequence_completion"


def export_snapshot(graph: dict[str, Any], manifest: dict[str, Any], created_at: str | None = None) -> dict[str, Any]:
    created_at = created_at or datetime.now(timezone.utc).isoformat()
    nodes = graph.get("nodes") or {}
    edges = graph.get("edges") or []
    snapshot_ref = manifest.get("snapshot_ref") or f".grapher/shared/history/{manifest.get('publication_id')}.json"
    source_warning = manifest.get("source_warning")
    outgoing: dict[str, list[dict[str, Any]]] = defaultdict(list)
    contradicted: set[str] = set()
    for e in edges:
        if e.get("rel") == "contradicts": contradicted |= {str(e.get("from")), str(e.get("to"))}
        if e.get("rel") in ANTECEDENT_RELS:
            outgoing[str(e.get("from"))].append(e)

    examples = []
    reasons = Counter(); candidates = Counter(); rejected_kind = Counter(); seen = set()
    for target_id in sorted(nodes):
        target = nodes[target_id]
        if target.get("type") not in SEMANTIC_TYPES: continue
        linked, rels = set(), []
        for e in outgoing.get(target_id, []):
            other = str(e["to"])
            if other in nodes and other != target_id and nodes[other].get("type") in SEMANTIC_TYPES:
                linked.add(other); rels.append({"from":str(e["from"]),"to":str(e["to"]),"rel":str(e["rel"]),"note":e.get("note")})
        inputs = [nodes[i] for i in sorted(linked)]
        kind = kind_for(str(target.get("type")), {str(n.get("type")) for n in inputs})
        candidates[kind] += 1
        reject = []
        if not (isinstance(target.get("semantic"), dict) and target.get("semantic")): reject.append("target_not_canonical_semantic")
        if any(not (isinstance(n.get("semantic"), dict) and n.get("semantic")) for n in inputs): reject.append("input_not_canonical_semantic")
        if not inputs: reject.append("no_grounded_predecessor")
        if target.get("status") in EXCLUDED_TARGET_STATUSES: reject.append("target_excluded_status")
        if target_id in contradicted: reject.append("unresolved_contradiction")
        if target.get("type") in {"result","test","failure"} and not (evidence_refs(target) or target.get("verification") == "verified"): reject.append("outcome_without_evidence")
        if reject:
            reasons.update(reject); rejected_kind[kind] += 1; continue

        scopes = [target.get("scope") or {}, *(n.get("scope") or {} for n in inputs)]
        project = next((s.get("project_id") for s in scopes if s.get("project_id")), None)
        mission = next((s.get("mission_id") for s in scopes if s.get("mission_id")), None)
        generation = next((s.get("generation_id") for s in scopes if s.get("generation_id")), None)
        split_group = "/".join(str(x or "_") for x in (project,mission,generation)) if any((project,mission,generation)) else "component:"+sid(",".join(sorted([target_id,*linked])))
        strength = "verified" if target.get("verification") == "verified" and evidence_refs(target) else "partial" if target.get("verification") in {"verified","partially_verified"} else "declared" if evidence_refs(target) else "none"
        example = {
            "schema_version":"1.0",
            "example_id":"gx-"+sid(manifest["graph_hash"],kind,target_id,split_group),
            "example_kind":kind,"purpose":["evaluation","training"],
            "source":{"graph_hash":manifest["graph_hash"],"graph_version":int(manifest.get("version",1)),"snapshot_ref":str(snapshot_ref),"project_id":project,"mission_id":mission,"generation_id":generation,"episode_id":sid(split_group,target_id)},
            "input":{"records":[normalize(n) for n in inputs],"relations":[]},
            "target":{"records":[normalize(target)],"relations":sorted(rels,key=lambda r:(r["from"],r["to"],r["rel"]))},
            "quality":{"eligible":True,"policy_version":POLICY_VERSION,"evidence_strength":strength,"unresolved_contradiction":False,"target_superseded":False,"warnings":[str(source_warning)] if source_warning else []},
            "split_group":split_group,
            "export":{"exporter":"grapher-research-exporter","exporter_version":EXPORTER_VERSION,"created_at":created_at},
        }
        fp = hashlib.sha256(json.dumps({"kind":kind,"input":example["input"]["records"],"target":example["target"]["records"]},sort_keys=True).encode()).hexdigest()
        if fp in seen:
            reasons["duplicate_example"] += 1; rejected_kind[kind] += 1; continue
        seen.add(fp); examples.append(example)

    eligible = Counter(e["example_kind"] for e in examples)
    evidence = Counter(e["quality"]["evidence_strength"] for e in examples)
    groups = Counter(e["split_group"] for e in examples)
    total = sum(candidates.values())
    metrics = {
        "graph_hash":manifest["graph_hash"],"exporter_version":EXPORTER_VERSION,"policy_version":POLICY_VERSION,
        "source_warning":source_warning,
        "candidate_count":total,"eligible_count":len(examples),"rejected_count":total-len(examples),
        "eligibility_rate":round(len(examples)/total,4) if total else 0.0,
        "candidate_by_kind":dict(sorted(candidates.items())),"eligible_by_kind":dict(sorted(eligible.items())),
        "rejected_by_kind":dict(sorted(rejected_kind.items())),"rejection_reasons":dict(sorted(reasons.items())),
        "evidence_strength":dict(sorted(evidence.items())),"split_group_count":len(groups),"largest_split_group":max(groups.values(),default=0),
        "duplicate_fingerprints":reasons.get("duplicate_example",0),
    }
    return {"metrics":metrics,"examples":sorted(examples,key=lambda e:e["example_id"])}


def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument("--graph",default=".grapher/shared/knowledge.json"); p.add_argument("--manifest",default=".grapher/shared/manifest.json"); p.add_argument("--out"); p.add_argument("--metrics")
    a=p.parse_args(); result=export_snapshot(load(a.graph),load(a.manifest))
    if a.out: Path(a.out).write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    if a.metrics: Path(a.metrics).write_text(json.dumps(result["metrics"],indent=2,sort_keys=True)+"\n")
    if not (a.out or a.metrics): print(json.dumps(result["metrics"],indent=2,sort_keys=True))
    return 0

if __name__ == "__main__": raise SystemExit(main())
