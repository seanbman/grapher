"""One-shot curation for CASSIO brain per migration acceptance cases."""

from __future__ import annotations

import copy
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from grapher.infer import reset_truth_metadata
from grapher.graph import dedupe_edges, edge_exists
from grapher.model import make_edge, now_iso
from grapher.registry import CANONICAL_STAGE_ORDER
from grapher.store import save_graph_mutation

CORRUPTED_SCREENS = (
    "concept-screen-04",
    "concept-screen-12",
    "concept-screen-18",
    "concept-screen-21",
    "concept-screen-22",
    "concept-screen-23",
    "concept-screen-24",
)

CHECKPOINTS: list[dict[str, Any]] = [
    {
        "id": "checkpoint-current-audio-architecture",
        "title": "Current: audio architecture",
        "stage": "developing",
        "derived_from": [
            "finding-fx-library-sample-track",
            "finding-sample-level-vs-master",
            "finding-sample-keys-quiet-fix",
            "concept-area-sound",
        ],
        "content": (
            "Current winning audio stack (Sep 2026): shared FxChain/FxParams registry "
            "for samples and loop tracks; SampleVoice on FxChain; per-track loop engine. "
            "See finding-fx-library-sample-track (supersedes old sample-edit pages). "
            "Refresh with: grapher checkpoint refresh checkpoint-current-audio-architecture"
        ),
    },
    {
        "id": "checkpoint-current-sampler",
        "title": "Current: sampler",
        "stage": "developing",
        "derived_from": [
            "finding-sample-full-length-crop-saveas",
            "finding-sample-save-rename",
            "finding-hold-sample-loop",
            "concept-area-sound",
            "concept-screen-12",
        ],
        "content": "Current sampler UX and playback: full-length play, trim-aware Save As, gate behavior. See linked findings.",
    },
    {
        "id": "checkpoint-current-loop-engine",
        "title": "Current: loop engine",
        "stage": "developing",
        "derived_from": [
            "finding-loop-d2-step-sequencer",
            "finding-loop-d1",
            "concept-area-loop",
            "concept-screen-21",
            "concept-screen-24",
        ],
        "content": "Current loop engine: D1 track view + D2 step sequencer (Screens 21–25). finding-loop-d2-step-sequencer is canonical implementation truth.",
    },
    {
        "id": "checkpoint-current-ui-controls",
        "title": "Current: UI controls",
        "stage": "designing",
        "derived_from": [
            "finding-ui-fullbleed-layout",
            "finding-ui-knobs-viz-autoboot",
            "concept-area-ui",
        ],
        "content": "Current UI/control layer findings: layout, knobs, autoboot. Linked isolated UI findings apply here.",
    },
    {
        "id": "checkpoint-current-persistence",
        "title": "Current: persistence",
        "stage": "maintaining",
        "derived_from": [
            "finding-crash-persist-storm",
            "concept-persistence",
        ],
        "content": (
            "Persistence rule: debounced persist (600ms), flush on pagehide; never hot-path "
            "PCM clone on knob ticks. Incident finding-crash-persist-storm is verified historical truth."
        ),
    },
    {
        "id": "checkpoint-current-roadmap",
        "title": "Current: roadmap",
        "stage": "planning",
        "derived_from": [
            "finding-roadmap-bplus-then-c",
            "concept-cassio-project",
        ],
        "content": "Roadmap checkpoint: Milestone B+ factory voices/presets then C Sampler. Refresh from roadmap findings.",
    },
]

ISOLATED_LINKS: list[tuple[str, str, str]] = [
    ("finding-ui-fullbleed-layout", "concept-area-ui", "applies_to"),
    ("finding-ui-knobs-viz-autoboot", "concept-area-ui", "applies_to"),
    ("finding-ui-brand-keys-balance", "concept-area-ui", "applies_to"),
    ("finding-ui-no-text-select", "concept-area-ui", "applies_to"),
    ("finding-ui-midrow-axis-tighten", "concept-area-ui", "applies_to"),
    ("finding-octave-remap-held-midi", "concept-cassio-project", "applies_to"),
    ("finding-hold-toggle-sticky-pitch", "concept-area-sound", "applies_to"),
    ("finding-sample-edit-discoverability", "concept-area-sound", "applies_to"),
    ("finding-new-kit-create", "concept-area-sound", "applies_to"),
    ("finding-tap-tempo-feel", "concept-area-loop", "applies_to"),
    ("finding-drum-fx-delay-not-drive", "concept-area-loop", "applies_to"),
    ("finding-loop-full-length-on-stop", "concept-area-loop", "applies_to"),
    ("finding-loop-track-vol-vs-master", "concept-area-loop", "applies_to"),
    ("loop-track-level-nan-fix-a59c6ef9", "concept-area-loop", "applies_to"),
    ("loop-multi-track-timeline-hold-arrow-offset-scru-538b652b", "concept-area-loop", "applies_to"),
]

TRUTH_FIXES: dict[str, dict[str, Any]] = {
    "document-cassio-v1-complete-operating-man-7fc14f07b2": {
        "status": "canonical_spec",
        "stage": "designing",
        "verification": "not_applicable",
    },
    "finding-fx-library-sample-track": {
        "status": "current",
        "stage": "developing",
        "verification": "partially_verified",
    },
    "finding-sample-edit-pages-fx": {
        "status": "superseded",
        "stage": "developing",
        "verification": "not_applicable",
    },
    "finding-crash-persist-storm": {
        "status": "historical",
        "stage": "maintaining",
        "verification": "verified",
        "evidence": [
            {
                "type": "observation",
                "ref": "runtime",
                "summary": "710 persist recovery writes; 55/s bursts; 8.19MB PCM clones",
            },
            {
                "type": "test",
                "ref": "headless",
                "summary": "60 rapid knob ticks → 1 write after debounce fix",
            },
        ],
    },
    "finding-sample-full-length-crop-saveas": {
        "status": "current",
        "stage": "developing",
        "verification": "partially_verified",
    },
    "finding-loop-d2-step-sequencer": {
        "status": "current",
        "stage": "developing",
        "verification": "verified",
        "evidence": [
            {
                "type": "test",
                "ref": "smoke",
                "summary": "Smoke tests documented in finding content",
            }
        ],
    },
}


def _backup(path: Path) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = path.with_name(f"knowledge.pre-curate-backup-{ts}.json")
    shutil.copy2(path, dest)
    return dest


def _find_image_for_concept(graph: dict[str, Any], concept_id: str) -> dict[str, Any] | None:
    nodes = graph["nodes"]
    for e in graph.get("edges") or []:
        if e.get("to") == concept_id and e.get("rel") == "depicts":
            img = nodes.get(e["from"])
            if img and img.get("type") == "image":
                return img
        if e.get("from") == concept_id and e.get("rel") == "depicts":
            img = nodes.get(e["to"])
            if img and img.get("type") == "image":
                return img
    # fallback: screen number in id
    m = re.search(r"screen-(\d+)", concept_id)
    if not m:
        return None
    num = m.group(1)
    for nid, n in nodes.items():
        if n.get("type") == "image" and f"screen-{num}" in nid:
            return n
    return None


def _repair_concept_content(concept: dict[str, Any], image: dict[str, Any] | None) -> str:
    title = concept.get("title") or "Screen"
    parts = [f"{title}."]
    if image and (image.get("content") or "").strip():
        parts.append(f"UI (from mockup): {image['content'].strip()}")
    # salvage non-garbled tail from original if present
    orig = concept.get("content") or ""
    if "WHAT IT DOES" in orig or "NOTES:" in orig:
        idx = orig.find("WHAT IT DOES")
        if idx == -1:
            idx = orig.find("NOTES:")
        if idx > 0:
            parts.append(orig[idx:].strip())
    elif len(orig) > 200 and orig.count("  ") < 5:
        parts.append(orig.split("\n", 1)[-1].strip()[:800])
    parts.append(
        "NOTE: concept text repaired from corrupted manual extraction; "
        "prefer linked image node and finding nodes for implementation truth."
    )
    return "\n\n".join(parts)


def _upgrade_related_to_supersedes(graph: dict[str, Any]) -> int:
    upgraded = 0
    for e in graph.get("edges") or []:
        if e.get("rel") != "related":
            continue
        note = (e.get("note") or "").lower()
        if "supersedes" in note:
            e["rel"] = "supersedes"
            upgraded += 1
    return upgraded


def curate_cassio(
    graph_path: Path,
    *,
    dry_run: bool = False,
    source: str = "cli",
    context: dict[str, Any] | None = None,
    actor: dict[str, Any] | None = None,
    reason: str | None = None,
    evidence_refs: list[str] | None = None,
    decision_ids: list[str] | None = None,
    requirement_ids: list[str] | None = None,
    supersedes: list[str] | None = None,
    overrides: list[str] | None = None,
    operation_id: str | None = None,
    phase: str = "executed",
) -> dict[str, Any]:
    graph_path = graph_path.resolve()
    with graph_path.open(encoding="utf-8") as f:
        graph = json.load(f)
    original = copy.deepcopy(graph)

    report: dict[str, Any] = {
        "action": "curate_cassio",
        "dry_run": dry_run,
        "path": str(graph_path),
    }

    if not dry_run:
        report["backup"] = str(_backup(graph_path))

    reset_truth_metadata(graph)

    graph["version"] = 2
    graph["graph"] = {
        "name": "cassio-brain",
        "domain": "software",
        "kinds": ["knowledge", "design", "implementation", "decision", "operations"],
        "stages": list(CANONICAL_STAGE_ORDER),
        "profile": "software",
        "created_at": graph.get("graph", {}).get("created_at") or now_iso(),
        "updated_at": now_iso(),
    }

    # Truth fixes
    for nid, fields in TRUTH_FIXES.items():
        node = graph["nodes"].get(nid)
        if not node:
            continue
        for k, v in fields.items():
            node[k] = v
        meta = dict(node.get("meta") or {})
        meta["curation"] = {"source": "cassio_acceptance", "at": now_iso()}
        node["meta"] = meta

    # Supersedes edge (explicit)
    if not edge_exists(
        graph,
        "finding-fx-library-sample-track",
        "finding-sample-edit-pages-fx",
        "supersedes",
    ):
        graph["edges"].append(
            make_edge(
                from_id="finding-fx-library-sample-track",
                to_id="finding-sample-edit-pages-fx",
                rel="supersedes",
                note="Sample Edit pages replaced by collapsible FX settings list",
            )
        )

    upgraded = _upgrade_related_to_supersedes(graph)
    report["related_upgraded_to_supersedes"] = upgraded

    # Acceptance-case precise relations
    pairs = [
        ("finding-loop-d2-step-sequencer", "concept-screen-24", "implements"),
        ("finding-crash-persist-storm", "concept-persistence", "applies_to"),
        ("finding-fx-library-sample-track", "concept-area-sound", "applies_to"),
    ]
    for frm, to, rel in pairs:
        if frm in graph["nodes"] and to in graph["nodes"]:
            if not edge_exists(graph, frm, to, rel):
                graph["edges"].append(make_edge(from_id=frm, to_id=to, rel=rel))

    # Repair corrupted concepts
    repaired = []
    for cid in CORRUPTED_SCREENS:
        concept = graph["nodes"].get(cid)
        if not concept:
            continue
        img = _find_image_for_concept(graph, cid)
        concept["content"] = _repair_concept_content(concept, img)
        meta = dict(concept.get("meta") or {})
        meta["repaired_at"] = now_iso()
        meta["repair_source"] = "cassio_curate"
        concept["meta"] = meta
        concept["stage"] = "designing"
        concept["status"] = "canonical_spec"
        concept["verification"] = "not_applicable"
        repaired.append(cid)
    report["concepts_repaired"] = repaired

    # Checkpoints (stable ids)
    created_ck = []
    for ck in CHECKPOINTS:
        ck_id = ck["id"]
        if ck_id in graph["nodes"]:
            continue
        ts = now_iso()
        graph["nodes"][ck_id] = {
            "id": ck_id,
            "type": "checkpoint",
            "title": ck["title"],
            "content": ck["content"],
            "path": None,
            "tags": ["checkpoint", "cassio"],
            "meta": {"created_by": "cassio_curate"},
            "status": "current",
            "workflow_state": "active",
            "verification": "partially_verified",
            "stage": ck.get("stage", "developing"),
            "evidence": [],
            "source_refs": [],
            "owners": [],
            "created_at": ts,
            "updated_at": ts,
        }
        for src in ck.get("derived_from") or []:
            if src in graph["nodes"] and not edge_exists(graph, ck_id, src, "derived_from"):
                graph["edges"].append(
                    make_edge(from_id=ck_id, to_id=src, rel="derived_from", note="checkpoint scope")
                )
        created_ck.append(ck_id)
    report["checkpoints_created"] = created_ck

    # Connect isolated nodes
    linked = 0
    for frm, to, rel in ISOLATED_LINKS:
        if frm in graph["nodes"] and to in graph["nodes"]:
            if not edge_exists(graph, frm, to, rel):
                graph["edges"].append(make_edge(from_id=frm, to_id=to, rel=rel))
                linked += 1
    report["isolated_linked"] = linked

    report["edges_deduped"] = dedupe_edges(graph)

    report["nodes"] = len(graph["nodes"])
    report["edges"] = len(graph["edges"])

    if not dry_run:
        mutation_context = {"kind": "cassio_acceptance"}
        if context:
            mutation_context.update(context)
        save_graph_mutation(
            graph_path,
            graph,
            action="curation_applied",
            before=original,
            source=source,
            context=mutation_context,
            actor=actor,
            reason=reason,
            evidence_refs=evidence_refs,
            decision_ids=decision_ids,
            requirement_ids=requirement_ids,
            supersedes=supersedes,
            overrides=overrides,
            operation_id=operation_id,
            phase=phase,
        )
        # sync config
        cfg_path = graph_path.parent / "config.json"
        cfg_path.write_text(
            json.dumps(
                {
                    "profile": "software",
                    "domain": "software",
                    "kinds": graph["graph"]["kinds"],
                    "stages": graph["graph"]["stages"],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    return report
