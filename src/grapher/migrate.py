"""Migrate v1 graphs to v2 with optional previewed inference."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from grapher.config import default_config, load_config, save_config
from grapher.infer import apply_inference, preview_inference, reset_truth_metadata, sort_stages
from grapher.model import now_iso
from grapher.registry import CANONICAL_STAGE_ORDER
from grapher.store import save_graph_mutation


def _backup_path(graph_path: Path) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return graph_path.with_name(f"knowledge.v1-backup-{ts}.json")


def migrate_v1_to_v2(
    data: dict[str, Any],
    *,
    name: str | None = None,
    domain: str = "general",
    kinds: list[str] | None = None,
    stages: list[str] | None = None,
    profile: str = "general",
) -> dict[str, Any]:
    """Schema-only migration. Does not infer truth metadata."""
    if int(data.get("version", 1)) >= 2:
        return data

    ts = now_iso()
    graph_name = name or "knowledge"
    stage_list = sort_stages(stages or list(CANONICAL_STAGE_ORDER))
    out: dict[str, Any] = {
        "version": 2,
        "graph": {
            "name": graph_name,
            "domain": domain,
            "kinds": kinds or ["knowledge"],
            "stages": stage_list,
            "profile": profile,
            "migrated_at": ts,
            "updated_at": ts,
        },
        "nodes": {},
        "edges": list(data.get("edges") or []),
    }

    for nid, node in (data.get("nodes") or {}).items():
        out["nodes"][nid] = dict(node)

    return out


def run_migrate(
    graph_path: Path,
    *,
    to_version: int = 2,
    dry_run: bool = False,
    infer: bool = False,
    approve_infer: bool = False,
    yes: bool = False,
    domain: str | None = None,
    kinds: list[str] | None = None,
    stages: list[str] | None = None,
    profile: str | None = None,
    name: str | None = None,
    only_high_confidence: bool = False,
    no_backup: bool = False,
) -> dict[str, Any]:
    with graph_path.open(encoding="utf-8") as f:
        data = json.load(f)

    current = int(data.get("version", 1))

    if infer and not approve_infer and not dry_run:
        raise ValueError(
            "automatic inference requires --approve-infer (use --dry-run --infer to preview first)"
        )

    if current >= to_version and not infer:
        return {
            "action": "migrate",
            "status": "already_current",
            "version": current,
            "path": str(graph_path),
            "nodes": len(data.get("nodes") or {}),
            "edges": len(data.get("edges") or []),
        }

    if to_version != 2:
        raise ValueError(f"unsupported target version: {to_version}")

    cfg = load_config(graph_path)
    if current >= to_version:
        migrated = dict(data)
        # Refresh graph metadata if explicitly provided
        if any([name, domain, kinds, stages, profile]):
            gmeta = dict(migrated.get("graph") or {})
            if name:
                gmeta["name"] = name
            if domain:
                gmeta["domain"] = domain
            if kinds:
                gmeta["kinds"] = kinds
            if stages:
                gmeta["stages"] = sort_stages(stages)
            if profile:
                gmeta["profile"] = profile
            migrated["graph"] = gmeta
    else:
        migrated = migrate_v1_to_v2(
            data,
            name=name or graph_path.stem,
            domain=domain or cfg.get("domain", "general"),
            kinds=kinds or cfg.get("kinds"),
            stages=sort_stages(stages or cfg.get("stages") or list(CANONICAL_STAGE_ORDER)),
            profile=profile or cfg.get("profile", "general"),
        )

    infer_report = None
    if infer:
        infer_report = preview_inference(migrated)
        if approve_infer and not dry_run:
            apply_inference(
                migrated,
                only_high_confidence=only_high_confidence,
                include_stages=not only_high_confidence,
                include_edges=True,
            )

    report: dict[str, Any] = {
        "action": "migrate",
        "status": "dry_run" if dry_run else "migrated",
        "from_version": current,
        "to_version": 2,
        "path": str(graph_path),
        "nodes": len(migrated["nodes"]),
        "edges": len(migrated["edges"]),
        "inferred": infer,
        "approve_infer": approve_infer,
        "backup": None,
    }

    if infer_report:
        report["inference"] = {
            "nodes_with_inferences": infer_report["nodes_with_inferences"],
            "status_counts": infer_report["status_counts"],
            "proposed_edges": infer_report["proposed_edges"],
        }
        if dry_run or (infer and not approve_infer):
            report["inference"]["records"] = infer_report["records"]
            report["inference"]["edges"] = infer_report["edges"]

    if dry_run:
        report["preview"] = {"graph": migrated["graph"]}
        return report

    if not yes:
        raise ValueError("migration requires --yes (use --dry-run to preview)")

    if current < to_version or infer:
        if current < to_version and not no_backup:
            backup = _backup_path(graph_path)
            shutil.copy2(graph_path, backup)
            report["backup"] = str(backup)
        elif infer and approve_infer and not no_backup:
            backup = graph_path.with_name(
                f"knowledge.pre-infer-backup-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
            )
            shutil.copy2(graph_path, backup)
            report["backup"] = str(backup)

    from grapher.audit import validate_graph
    validation = validate_graph(migrated, graph_path)
    if not validation["valid"]:
        raise ValueError(f"migrated graph failed validation: {validation['issues']}")
    save_graph_mutation(graph_path, migrated, action="migration_completed", before=data,
                        context={"from_version": current, "to_version": 2})

    cfg_path = graph_path.parent / "config.json"
    if not cfg_path.is_file():
        save_config(
            graph_path,
            default_config(profile=migrated["graph"].get("profile", "general")),
        )

    return report


def run_infer_preview(graph_path: Path) -> dict[str, Any]:
    with graph_path.open(encoding="utf-8") as f:
        data = json.load(f)
    return preview_inference(data)


def run_infer_apply(
    graph_path: Path,
    *,
    yes: bool = False,
    dry_run: bool = False,
    only_high_confidence: bool = False,
) -> dict[str, Any]:
    with graph_path.open(encoding="utf-8") as f:
        data = json.load(f)
    if dry_run:
        return preview_inference(data)
    if not yes:
        raise ValueError("infer apply requires --yes (use --dry-run to preview)")
    summary = apply_inference(
        data,
        only_high_confidence=only_high_confidence,
        include_stages=not only_high_confidence,
    )
    save_graph_mutation(graph_path, data, action="curation_applied", before=None,
                        context={"kind": "inference"})
    summary["path"] = str(graph_path)
    return summary


def run_reset_truth(graph_path: Path, *, yes: bool = False, dry_run: bool = False) -> dict[str, Any]:
    with graph_path.open(encoding="utf-8") as f:
        data = json.load(f)
    preview = reset_truth_metadata(data)
    if dry_run:
        preview["status"] = "dry_run"
        return preview
    if not yes:
        raise ValueError("reset-truth requires --yes")
    save_graph_mutation(graph_path, data, action="curation_applied", before=None,
                        context={"kind": "reset_truth"})
    preview["status"] = "reset"
    preview["path"] = str(graph_path)
    return preview
