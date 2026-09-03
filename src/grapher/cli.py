"""grapher CLI — project-local knowledge graph for Cursor agents."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from grapher import graph as G
from grapher.embed import EmbedError
from grapher.model import BUILTIN_NODE_TYPES, NODE_TYPES, embed_text, now_iso
from grapher.registry import (
    GRAPH_KINDS,
    LIFECYCLE_STAGES,
    PROFILES,
    PROFILE_DEFAULTS,
    TRUTH_STATUSES,
    WORKFLOW_STATES,
    VERIFICATION_STATES,
    PROVENANCE_INTEGRITIES,
    parse_repeatable,
    validate_kinds,
    validate_stages,
)
from grapher import search as S
from grapher.format import emit
from grapher.store import (
    init_store,
    load_graph,
    load_vectors,
    resolve_graph_path,
    save_graph,
    save_graph_mutation,
    vectors_path_for,
)


def _out(data: Any, args: argparse.Namespace) -> None:
    emit(data, as_json=getattr(args, "json", False))


def _die(msg: str, code: int = 1) -> None:
    print(msg, file=sys.stderr)
    raise SystemExit(code)


def _parse_tags(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [t.strip() for t in raw.split(",") if t.strip()]


def _json_values(values: list[str] | None, label: str) -> list[dict[str, Any]] | None:
    if values is None:
        return None
    out = []
    for raw in values:
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            _die(f"invalid {label} JSON: {exc}")
        if not isinstance(value, dict):
            _die(f"{label} must be a JSON object")
        out.append(value)
    return out


def _scope_and_provenance(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    scope = {
        "workspace_id": getattr(args, "workspace", None) or os.environ.get("GRAPHER_WORKSPACE_ID"),
        "project_id": getattr(args, "project", None) or os.environ.get("GRAPHER_PROJECT_ID"),
        "mission_id": getattr(args, "mission", None) or os.environ.get("GRAPHER_MISSION_ID"),
        "generation_id": getattr(args, "generation", None) or os.environ.get("GRAPHER_GENERATION_ID"),
    }
    scope = {k: v for k, v in scope.items() if v}
    provenance = {
        "actor_id": getattr(args, "actor", None) or os.environ.get("GRAPHER_ACTOR_ID"),
        "actor_kind": getattr(args, "actor_kind", None) or os.environ.get("GRAPHER_ACTOR_KIND"),
        "actor_role": getattr(args, "role", None) or os.environ.get("GRAPHER_ACTOR_ROLE"),
        "session_id": getattr(args, "session", None) or os.environ.get("GRAPHER_SESSION_ID"),
        "source": getattr(args, "source", None) or os.environ.get("GRAPHER_SOURCE") or "cli",
        "attestation_ref": getattr(args, "attestation", None) or os.environ.get("GRAPHER_ATTESTATION_REF"),
    }
    integrity = getattr(args, "provenance_integrity", None)
    if integrity == "verified" and not provenance.get("attestation_ref"):
        _die("verified provenance requires --attestation or GRAPHER_ATTESTATION_REF")
    supplied = any(provenance.get(k) for k in ("actor_id", "actor_kind", "actor_role", "session_id", "attestation_ref")) or integrity or getattr(args, "source", None) or os.environ.get("GRAPHER_SOURCE")
    if supplied:
        provenance["integrity"] = integrity or ("declared" if provenance.get("actor_id") else "unknown")
        provenance["recorded_at"] = now_iso()
        provenance = {k: v for k, v in provenance.items() if v}
    else:
        provenance = {}
    return scope, provenance


def _mutation_source(args: argparse.Namespace) -> str:
    return getattr(args, "source", None) or os.environ.get("GRAPHER_SOURCE") or "cli"


def _history_actor(provenance: dict[str, Any]) -> dict[str, Any] | None:
    actor = {
        "kind": provenance.get("actor_kind"),
        "id": provenance.get("actor_id"),
        "role": provenance.get("actor_role"),
        "session_id": provenance.get("session_id"),
        "source": provenance.get("source"),
    }
    actor = {key: value for key, value in actor.items() if value is not None}
    return actor or None


def _history_kwargs(
    args: argparse.Namespace,
    *,
    scope: dict[str, Any] | None = None,
    provenance: dict[str, Any] | None = None,
    extra_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if scope is None or provenance is None:
        scope, provenance = _scope_and_provenance(args)
    context: dict[str, Any] = {}
    if scope:
        context["scope"] = scope
    if provenance:
        context["provenance"] = provenance
    if extra_context:
        context.update(extra_context)
    return {
        "source": _mutation_source(args),
        "context": context or None,
        "actor": _history_actor(provenance),
        "reason": getattr(args, "reason", None),
        "operation_id": getattr(args, "operation_id", None),
        "phase": getattr(args, "phase", "executed"),
        "evidence_refs": getattr(args, "history_evidence_ref", None),
        "decision_ids": getattr(args, "decision_id", None),
        "requirement_ids": getattr(args, "requirement_id", None),
        "overrides": getattr(args, "overrides_transition", None),
        "supersedes": getattr(args, "supersedes_transition", None),
    }


def _require_administrative_attribution(
    args: argparse.Namespace,
    provenance: dict[str, Any],
    *,
    flag: str,
) -> None:
    missing: list[str] = []
    if not provenance.get("actor_id"):
        missing.append("--actor or GRAPHER_ACTOR_ID")
    if not getattr(args, "reason", None):
        missing.append("--reason")
    if missing:
        _die(f"{flag} requires explicit {' and '.join(missing)}")


def _add_mutation_context_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--workspace", default=None)
    parser.add_argument("--project", default=None)
    parser.add_argument("--mission", default=None)
    parser.add_argument("--generation", default=None)
    parser.add_argument("--actor", default=None)
    parser.add_argument("--actor-kind", choices=["human", "agent", "system_tool", "migration_import"], default=None)
    parser.add_argument("--role", default=None)
    parser.add_argument("--session", default=None)
    parser.add_argument("--source", default=None)


def _add_mutation_history_args(
    parser: argparse.ArgumentParser,
    *,
    include_reason: bool = True,
) -> None:
    if include_reason:
        parser.add_argument("--reason", default=None, help="rationale recorded with every resulting transition")
    parser.add_argument("--operation-id", default=None, help="correlate changes belonging to one action")
    parser.add_argument("--phase", choices=["proposed", "executed", "observed", "verified", "canonical"], default="executed")
    parser.add_argument("--history-evidence-ref", action="append", default=None)
    parser.add_argument("--decision-id", action="append", default=None)
    parser.add_argument("--requirement-id", action="append", default=None)
    parser.add_argument("--overrides-transition", action="append", default=None)
    parser.add_argument("--supersedes-transition", action="append", default=None)

def _graph_path(args: argparse.Namespace, *, create: bool = False) -> Path:
    try:
        return resolve_graph_path(getattr(args, "graph", None), create=create)
    except FileNotFoundError as e:
        _die(str(e))


def cmd_init(args: argparse.Namespace) -> None:
    profile = args.profile or "general"
    profile_defaults = PROFILE_DEFAULTS[profile]
    kinds = parse_repeatable(args.kind) if args.kind else list(profile_defaults["kinds"])
    if args.all_stages:
        stages = list(LIFECYCLE_STAGES)
    else:
        stages = parse_repeatable(args.stage) if args.stage else list(profile_defaults["stages"])
    try:
        kinds = validate_kinds(kinds)
        stages = validate_stages(stages)
    except ValueError as e:
        _die(str(e))
    if profile not in PROFILES:
        _die(f"unknown profile {profile!r}; choose from {sorted(PROFILES)}")
    path = resolve_graph_path(args.graph, create=True)
    name = args.name or path.stem
    gpath, vpath = init_store(
        path,
        name=name,
        domain=args.domain or profile_defaults["domain"],
        kinds=kinds,
        stages=stages,
        profile=profile,
    )
    _out(
        {
            "graph": str(gpath),
            "vectors": str(vpath),
            "created": True,
            "version": 2,
            "kinds": kinds,
            "stages": stages,
            "domain": args.domain or profile_defaults["domain"],
            "profile": profile,
            "next": "grapher cursor install",
        },
        args,
    )


def cmd_add(args: argparse.Namespace) -> None:
    from grapher.config import allowed_node_types, canonical_stage, load_config

    path = _graph_path(args, create=True)
    if not path.is_file():
        init_store(path)
    before = load_graph(path, normalize=False)
    g = load_graph(path)
    cfg = load_config(path)
    allowed = allowed_node_types(cfg)
    if args.stage:
        args.stage = canonical_stage(args.stage, cfg)
        try:
            args.stage = validate_stages([args.stage])[0]
        except ValueError as exc:
            _die(str(exc))
    if args.type not in allowed:
        _die(f"unknown node type {args.type!r}; configure it in custom_node_types")
    content = sys.stdin.read() if args.content == "-" else args.content
    tags = _parse_tags(args.tags) if args.tags is not None else None
    scope, provenance = _scope_and_provenance(args)
    if args.force_finalized:
        _require_administrative_attribution(args, provenance, flag="--force-finalized")
    try:
        node = G.add_node(
            g, type=args.type, title=args.title, content=content, path=args.path,
            tags=tags, id=args.id, stage=args.stage, status=args.status,
            workflow_state=args.workflow_state, verification=args.verification,
            evidence=_json_values(args.evidence, "evidence"),
            source_refs=_parse_tags(args.source_refs) if args.source_refs is not None else None,
            owners=_parse_tags(args.owners) if args.owners is not None else None,
            scope=scope or None, provenance=provenance or None,
            finalized_at=now_iso() if args.finalize else None,
            force_finalized=args.force_finalized,
        )
    except (ValueError, G.GraphError) as exc:
        _die(str(exc))
    old = before.get("nodes", {}).get(node["id"])
    action = "node_updated" if old else "node_created"
    if args.finalize:
        action = "node_finalized"
    save_graph_mutation(
        path,
        g,
        action=action,
        target=node["id"],
        before=before,
        **_history_kwargs(
            args,
            scope=scope,
            provenance=provenance,
            extra_context={"force_finalized": args.force_finalized},
        ),
    )
    if old is None or embed_text(old) != embed_text(node):
        try:
            S.upsert_node_vector(path, node)
        except EmbedError:
            pass
    _out(node, args)


def cmd_scan(args: argparse.Namespace) -> None:
    from grapher.ingest import scan_directory

    path = _graph_path(args, create=True)
    if not path.is_file():
        init_store(path)
    g = load_graph(path)
    types = set(args.types.split(",")) if args.types else None
    try:
        result = scan_directory(
            g,
            Path(args.directory),
            graph_path=path,
            glob=args.glob,
            types=types,
            max_files=args.max_files,
        )
    except FileNotFoundError as e:
        _die(str(e))
    _out(result, args)


def cmd_ingest(args: argparse.Namespace) -> None:
    from grapher.ingest import ingest_directory

    path = _graph_path(args, create=True)
    if not path.is_file():
        init_store(path)
    before = load_graph(path, normalize=False)
    g = load_graph(path)
    types = set(args.types.split(",")) if args.types else None
    try:
        result = ingest_directory(
            g,
            Path(args.directory),
            graph_path=path,
            glob=args.glob,
            types=types,
            max_files=args.max_files,
            create_stubs=not args.no_stubs,
        )
    except FileNotFoundError as e:
        _die(str(e))
    if result.get("created_stubs", 0):
        scope, provenance = _scope_and_provenance(args)
        save_graph_mutation(
            path,
            g,
            action="ingest_queued",
            before=before,
            **_history_kwargs(
                args,
                scope=scope,
                provenance=provenance,
                extra_context={"directory": args.directory, "created_stubs": result.get("created_stubs", 0)},
            ),
        )
    _out(result, args)


def cmd_link(args: argparse.Namespace) -> None:
    path = _graph_path(args)
    before = load_graph(path, normalize=False)
    g = load_graph(path)
    from grapher.config import allowed_relations, canonical_relation, load_config
    cfg = load_config(path)
    args.rel = canonical_relation(args.rel, cfg)
    if args.rel not in allowed_relations(cfg):
        _die(f"unknown relation {args.rel!r}; configure it in custom_relations")
    existed = G.edge_get(g, args.frm, args.to, args.rel) is not None
    try:
        edge = G.link(
            g,
            from_id=args.frm,
            to_id=args.to,
            rel=args.rel,
            note=args.note,
        )
    except G.GraphError as e:
        _die(str(e))
    if not existed:
        scope, provenance = _scope_and_provenance(args)
        save_graph_mutation(
            path,
            g,
            action="relationship_created",
            target=f"{args.frm}:{args.rel}:{args.to}",
            before=before,
            **_history_kwargs(args, scope=scope, provenance=provenance),
        )
    _out(edge, args)


def cmd_get(args: argparse.Namespace) -> None:
    path = _graph_path(args)
    g = load_graph(path)
    try:
        node = G.get_node(g, args.id)
    except G.GraphError as e:
        _die(str(e))
    _out({"node": node, "edges": G.adjacent_edges(g, args.id)}, args)


def cmd_search(args: argparse.Namespace) -> None:
    path = _graph_path(args)
    g = load_graph(path)
    try:
        results = S.search(
            g,
            path,
            args.query,
            mode=args.mode,
            type=args.type,
            tag=args.tag,
            status=args.status,
            stage=args.stage,
            verification=args.verification,
            workflow_state=args.workflow_state,
            project=args.project, mission=args.mission, generation=args.generation,
            actor=args.actor, role=args.role, as_of=args.as_of,
            exclude_superseded=args.exclude_superseded,
            current_only=args.current_only,
            limit=args.limit,
            truth_rank=not args.no_truth_rank,
            explain_ranking=args.explain_ranking,
            kind=args.kind,
        )
    except (EmbedError, ValueError) as e:
        _die(str(e))
    _out(
        {"query": args.query, "mode": args.mode, "results": results},
        args,
    )


def cmd_neighbors(args: argparse.Namespace) -> None:
    path = _graph_path(args)
    g = load_graph(path)
    try:
        result = G.neighbors(g, args.id, depth=args.depth)
    except G.GraphError as e:
        _die(str(e))
    _out(result, args)


def cmd_path(args: argparse.Namespace) -> None:
    path = _graph_path(args)
    g = load_graph(path)
    try:
        result = G.shortest_path(g, args.a, args.b)
    except G.GraphError as e:
        _die(str(e))
    _out(result, args)


def cmd_list(args: argparse.Namespace) -> None:
    path = _graph_path(args)
    g = load_graph(path)
    nodes = G.list_nodes(g, type=args.type, tag=args.tag)
    _out({"nodes": nodes, "count": len(nodes)}, args)


def cmd_rm(args: argparse.Namespace) -> None:
    path = _graph_path(args)
    before = load_graph(path, normalize=False)
    g = load_graph(path)
    try:
        G.remove_node(g, args.id)
    except G.GraphError as e:
        _die(str(e))
    scope, provenance = _scope_and_provenance(args)
    save_graph_mutation(
        path,
        g,
        action="node_removed",
        target=args.id,
        before=before,
        **_history_kwargs(args, scope=scope, provenance=provenance),
    )
    S.remove_node_vector(path, args.id)
    _out({"removed": args.id}, args)


def cmd_reindex(args: argparse.Namespace) -> None:
    path = _graph_path(args)
    g = load_graph(path)
    try:
        result = S.reindex(g, path)
    except EmbedError as e:
        _die(str(e))
    _out(result, args)


def cmd_export(args: argparse.Namespace) -> None:
    path = _graph_path(args)
    g = load_graph(path)
    if args.format == "mermaid":
        text = G.to_mermaid(g)
        if args.output:
            Path(args.output).write_text(text, encoding="utf-8")
            _out(
                {
                    "action": "pack",
                    "name": "export",
                    "path": str(Path(args.output).resolve()),
                    "nodes": len(g.get("nodes") or {}),
                    "edges": len(g.get("edges") or []),
                    "vectors": 0,
                    "description": "mermaid export",
                },
                args,
            )
        else:
            sys.stdout.write(text)
        return
    if args.output:
        Path(args.output).write_text(
            json.dumps(g, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        _out(
            {
                "action": "pack",
                "name": "export",
                "path": str(Path(args.output).resolve()),
                "nodes": len(g.get("nodes") or {}),
                "edges": len(g.get("edges") or []),
                "vectors": 0,
                "description": "json export",
            },
            args,
        )
        return
    _out(g, args)


def cmd_pack(args: argparse.Namespace) -> None:
    from grapher.transfer import TransferError, pack_graph

    path = _graph_path(args)
    try:
        result = pack_graph(
            path,
            Path(args.output),
            name=args.name or "",
            description=args.description or "",
            include_vectors=not args.no_vectors,
        )
    except (OSError, TransferError, FileNotFoundError, ValueError) as e:
        _die(str(e))
    _out(result, args)


def cmd_unpack(args: argparse.Namespace) -> None:
    from grapher.transfer import TransferError

    if getattr(args, "codex", False):
        from grapher.codex_cmd import codex_receive

        path = _graph_path(args, create=True)
        if not path.is_file():
            init_store(path)
        mode = "replace" if args.replace else args.mode
        try:
            result = codex_receive(
                Path(args.pack),
                graph=str(path),
                mode=mode,
                prefix=args.prefix or "",
                include_vectors=not args.no_vectors,
                force=False,
            )
        except (OSError, TransferError, FileNotFoundError, ValueError) as e:
            _die(str(e))
        _out(result, args)
        return

    from grapher.transfer import unpack_graph

    path = _graph_path(args, create=True)
    if not path.is_file():
        init_store(path)
    mode = "replace" if args.replace else args.mode
    try:
        result = unpack_graph(
            path,
            Path(args.pack),
            mode=mode,
            prefix=args.prefix or "",
            include_vectors=not args.no_vectors,
        )
    except (OSError, TransferError, FileNotFoundError, ValueError) as e:
        _die(str(e))
    _out(result, args)


def cmd_codex_install(args: argparse.Namespace) -> None:
    from grapher.codex_cmd import install_codex_integration

    result = install_codex_integration(
        graph=getattr(args, "graph", None),
        force=args.force,
        ensure_init=True,
    )
    _out(result, args)


def cmd_codex_status(args: argparse.Namespace) -> None:
    from grapher.codex_cmd import codex_status

    _out(codex_status(graph=getattr(args, "graph", None)), args)


def cmd_codex_context(args: argparse.Namespace) -> None:
    from grapher.codex_cmd import codex_context
    from grapher.transfer import TransferError

    try:
        result = codex_context(
            graph=getattr(args, "graph", None),
            from_pack=args.from_pack,
            output=args.output,
            name=args.name or "",
            description=args.description or "",
        )
    except (OSError, TransferError, FileNotFoundError, ValueError) as e:
        _die(str(e))
    _out(result, args)


def cmd_codex_export(args: argparse.Namespace) -> None:
    from grapher.codex_cmd import codex_export
    from grapher.transfer import TransferError

    try:
        result = codex_export(
            Path(args.directory),
            graph=getattr(args, "graph", None),
            name=args.name or "",
            description=args.description or "",
            include_vectors=not args.no_vectors,
        )
    except (OSError, TransferError, FileNotFoundError, ValueError) as e:
        _die(str(e))
    _out(result, args)


def cmd_codex_receive(args: argparse.Namespace) -> None:
    from grapher.codex_cmd import codex_receive
    from grapher.transfer import TransferError

    mode = "replace" if args.replace else args.mode
    try:
        result = codex_receive(
            Path(args.source),
            graph=getattr(args, "graph", None),
            mode=mode,
            prefix=args.prefix or "",
            include_vectors=not args.no_vectors,
            force=args.force,
        )
    except (OSError, TransferError, FileNotFoundError, ValueError) as e:
        _die(str(e))
    _out(result, args)


def cmd_stat(args: argparse.Namespace) -> None:
    path = _graph_path(args)
    g = load_graph(path)
    vpath = vectors_path_for(path)
    vectors = load_vectors(vpath) if vpath.is_file() else None
    _out(G.stats(g, vectors), args)


def cmd_cursor_install(args: argparse.Namespace) -> None:
    from grapher.cursor_cmd import install_cursor_integration

    result = install_cursor_integration(
        graph=getattr(args, "graph", None),
        force=args.force,
        ensure_init=True,
    )
    _out(result, args)


def cmd_cursor_status(args: argparse.Namespace) -> None:
    from grapher.cursor_cmd import cursor_status

    result = cursor_status(graph=getattr(args, "graph", None))
    _out(result, args)


def cmd_validate(args: argparse.Namespace) -> None:
    from grapher.audit import validate_graph

    path = _graph_path(args)
    g = load_graph(path)
    _out(validate_graph(g, path), args)


def cmd_audit(args: argparse.Namespace) -> None:
    from grapher.audit import audit_graph

    path = _graph_path(args)
    g = load_graph(path)
    _out(audit_graph(g, path), args)


def cmd_history(args: argparse.Namespace) -> None:
    from grapher.provenance import load_history

    path = _graph_path(args)
    entries = load_history(
        path, entity_id=args.entity, operation_id=args.operation,
        event_type=args.event_type, limit=args.limit,
    )
    _out({"history": entries, "count": len(entries)}, args)


def cmd_migrate(args: argparse.Namespace) -> None:
    from grapher.migrate import run_infer_apply, run_infer_preview, run_migrate, run_reset_truth

    path = _graph_path(args)
    sub = getattr(args, "migrate_command", None)

    if sub == "infer-preview":
        _out(run_infer_preview(path), args)
        return
    if sub == "infer-apply":
        try:
            result = run_infer_apply(
                path,
                yes=args.yes,
                dry_run=args.dry_run,
                only_high_confidence=args.only_high_confidence,
            )
        except ValueError as e:
            _die(str(e))
        _out(result, args)
        return
    if sub == "reset-truth":
        try:
            result = run_reset_truth(path, yes=args.yes, dry_run=args.dry_run)
        except ValueError as e:
            _die(str(e))
        _out(result, args)
        return

    kinds = parse_repeatable(args.kind) if args.kind else None
    stages = parse_repeatable(args.stage) if args.stage else None
    try:
        result = run_migrate(
            path,
            to_version=args.to,
            dry_run=args.dry_run,
            infer=args.infer,
            approve_infer=args.approve_infer,
            yes=args.yes,
            domain=args.domain,
            kinds=kinds,
            stages=stages,
            profile=args.profile,
            name=args.name,
            only_high_confidence=args.only_high_confidence,
            no_backup=getattr(args, "no_backup", False),
        )
    except ValueError as e:
        _die(str(e))
    _out(result, args)


def cmd_curate(args: argparse.Namespace) -> None:
    from grapher import curate as C

    path = _graph_path(args)
    sub = args.curate_command

    if sub == "cassio":
        from grapher.cassio_curate import curate_cassio
        scope, provenance = _scope_and_provenance(args)

        try:
            result = curate_cassio(
                path,
                dry_run=args.dry_run,
                **_history_kwargs(
                    args,
                    scope=scope,
                    provenance=provenance,
                    extra_context={"kind": "cassio_acceptance"},
                ),
            )
        except (ValueError, G.GraphError) as e:
            _die(str(e))
        _out(result, args)
        return

    before = load_graph(path, normalize=False)
    g = load_graph(path)
    dry = args.dry_run
    try:
        if sub == "status":
            result = C.set_status(g, args.id, args.status, dry_run=dry)
        elif sub == "relate":
            result = C.relate(
                g, args.frm, args.to, args.rel, note=args.note, dry_run=dry
            )
        elif sub == "supersede":
            result = C.supersede(
                g, args.new_id, args.old_id, note=args.note, dry_run=dry
            )
        elif sub == "merge":
            result = C.merge_nodes(g, args.keep, args.drop, dry_run=dry)
        elif sub == "compact":
            result = C.compact_related(g, topic=args.topic, dry_run=dry, limit=args.limit)
        elif sub == "finalize":
            result = C.finalize_node(g, args.id, dry_run=dry)
        elif sub == "provenance":
            result = C.set_provenance_integrity(
                g, args.id, args.integrity, reason=args.reason,
                attestation_ref=args.attestation, dry_run=dry
            )
        elif sub == "alias-rels":
            from grapher.config import load_config
            from grapher.relation_aliases import alias_relations

            cfg = load_config(path)
            result = alias_relations(
                g,
                aliases=cfg.get("relation_aliases") or None,
                dry_run=dry,
            )
        else:
            _die(f"unknown curate command: {sub}")
            return
    except (ValueError, G.GraphError) as e:
        _die(str(e))
    if not dry:
        action = {"status": "status_changed", "supersede": "node_superseded",
                  "merge": "node_merged", "finalize": "node_finalized",
                  "provenance": "provenance_changed"}.get(sub, "curation_applied")
        if sub == "status":
            target = args.id
        elif sub == "relate":
            target = f"{args.frm}:{args.rel}:{args.to}"
        elif sub == "supersede":
            target = args.old_id
        elif sub == "merge":
            target = args.keep
        elif sub in {"finalize", "provenance"}:
            target = args.id
        else:
            target = None
        scope, provenance = _scope_and_provenance(args)
        save_graph_mutation(
            path,
            g,
            action=action,
            target=target,
            before=before,
            **_history_kwargs(
                args,
                scope=scope,
                provenance=provenance,
                extra_context={"kind": sub},
            ),
        )
    _out(result, args)


def cmd_infer_links(args: argparse.Namespace) -> None:
    from grapher.linking import infer_from_config

    path = _graph_path(args)
    before = load_graph(path, normalize=False)
    g = load_graph(path)
    result = infer_from_config(g, path, dry_run=args.dry_run)
    if not args.dry_run and result.get("proposed", 0):
        scope, provenance = _scope_and_provenance(args)
        save_graph_mutation(
            path,
            g,
            action="curation_applied",
            before=before,
            **_history_kwargs(
                args,
                scope=scope,
                provenance=provenance,
                extra_context={"kind": "infer_links"},
            ),
        )
    _out(result, args)


def cmd_checkpoint(args: argparse.Namespace) -> None:
    from grapher import checkpoint as CK

    path = _graph_path(args)
    sub = args.checkpoint_command
    if sub == "list":
        _out(CK.list_checkpoints(path), args)
        return
    before = load_graph(path, normalize=False)
    g = load_graph(path)
    dry = args.dry_run
    try:
        if sub == "create":
            ids = [x.strip() for x in (args.nodes or "").split(",") if x.strip()] or None
            result = CK.create_checkpoint(
                g,
                path,
                title=args.title,
                content=args.content or "",
                node_ids=ids,
                status=args.status,
                dry_run=dry,
            )
        elif sub == "refresh":
            result = CK.refresh_checkpoint(
                g, path, args.id, dry_run=dry, yes=args.yes
            )
        else:
            _die(f"unknown checkpoint command: {sub}")
            return
    except ValueError as e:
        _die(str(e))
    if not dry and sub != "list":
        scope, provenance = _scope_and_provenance(args)
        save_graph_mutation(
            path,
            g,
            action=f"checkpoint_{sub}",
            target=result.get("id"),
            before=before,
            **_history_kwargs(
                args,
                scope=scope,
                provenance=provenance,
                extra_context={"kind": f"checkpoint_{sub}"},
            ),
        )
    _out(result, args)


def cmd_dash(args: argparse.Namespace) -> None:
    path = _graph_path(args, create=False)
    try:
        from grapher.viz.app import run_dashboard
    except ImportError as e:
        _die(str(e))
    try:
        run_dashboard(
            path,
            host=args.host,
            port=args.port,
            open_browser=args.open,
            debug=args.debug,
            view_mode=args.view,
        )
    except ImportError as e:
        _die(str(e))
    except OSError as e:
        _die(f"failed to start dashboard: {e}")


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--graph",
        help="path to knowledge.json (or set GRAPHER_GRAPH)",
    )
    common.add_argument(
        "--json",
        action="store_true",
        help="machine-readable JSON output (default is human text)",
    )

    p = argparse.ArgumentParser(
        prog="grapher",
        description=(
            "Project-local knowledge graph for Cursor and Codex agents — "
            "persist discoveries, search before acting, transplant ideas."
        ),
        epilog=(
            "examples:\n"
            "  grapher init && grapher cursor install && grapher codex install\n"
            "  grapher ingest ./docs   # then enrich pending nodes with deep content\n"
            "  grapher search \"auth tokens\" && grapher dash --open\n"
            "  grapher codex export ./kit/ && grapher codex receive ./kit/\n"
            "\n"
            "Run \"grapher help <command>\" for details (e.g. help codex, help ingest)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[common],
    )
    sub = p.add_subparsers(dest="command", required=True)

    def cmd_help(args: argparse.Namespace) -> None:
        topic = getattr(args, "topic", None)
        if not topic:
            p.print_help()
            return
        parts = topic.split()
        choice = sub.choices.get(parts[0])
        if choice is None:
            _die(f"unknown command: {topic}")
        if len(parts) == 1:
            choice.print_help()
            return
        for action in choice._actions:
            if isinstance(action, argparse._SubParsersAction):
                sub_choice = action.choices.get(parts[1])
                if sub_choice is None:
                    _die(f"unknown command: {topic}")
                sub_choice.print_help()
                return
        choice.print_help()

    s = sub.add_parser(
        "help",
        parents=[common],
        help="show help for grapher or a subcommand",
    )
    s.add_argument(
        "topic",
        nargs="?",
        default=None,
        help="command to describe (e.g. search, codex, cursor install)",
    )
    s.set_defaults(func=cmd_help)

    s = sub.add_parser(
        "init",
        parents=[common],
        help="create .grapher/ knowledge store (knowledge.json + vectors + config)",
    )
    s.add_argument(
        "--kind",
        action="append",
        default=None,
        help="graph kind(s); repeat or comma-separate (default: knowledge)",
    )
    s.add_argument(
        "--stage",
        action="append",
        default=None,
        help="lifecycle stage(s); repeat or comma-separate",
    )
    s.add_argument(
        "--all-stages",
        action="store_true",
        help="include all lifecycle stages",
    )
    s.add_argument(
        "--domain",
        default=None,
        help="free-form domain label (default: selected profile domain)",
    )
    s.add_argument(
        "--profile",
        default="general",
        choices=sorted(PROFILES),
        help="preset profile (default: general)",
    )
    s.add_argument(
        "--name",
        default=None,
        help="graph name (default: knowledge.json stem)",
    )
    s.set_defaults(func=cmd_init)

    cursor = sub.add_parser(
        "cursor",
        parents=[common],
        help="install or check Cursor rules/skills for grapher",
    )
    cursor_sub = cursor.add_subparsers(dest="cursor_command", required=True)
    c_install = cursor_sub.add_parser(
        "install",
        parents=[common],
        help="write .cursor rules/skills and ensure grapher init",
    )
    c_install.add_argument(
        "--force",
        action="store_true",
        help="overwrite existing rule/skill files",
    )
    c_install.set_defaults(func=cmd_cursor_install)
    c_status = cursor_sub.add_parser(
        "status",
        parents=[common],
        help="check whether Cursor integration is installed",
    )
    c_status.set_defaults(func=cmd_cursor_status)

    s = sub.add_parser(
        "add",
        parents=[common],
        help="add or upsert a node (title, type, content, path, tags)",
    )
    s.add_argument("--type", required=True)
    s.add_argument("--title", required=True)
    s.add_argument(
        "--content",
        default=None,
        help="summary text, or '-' to read from stdin",
    )
    s.add_argument("--path", default=None)
    s.add_argument("--tags", default=None, help="comma-separated tags")
    s.add_argument("--id", default=None, help="explicit node id (upsert if exists)")
    s.add_argument("--stage", default=None, help="canonical lifecycle stage")
    s.add_argument("--status", choices=sorted(TRUTH_STATUSES), default=None)
    s.add_argument("--workflow-state", choices=sorted(WORKFLOW_STATES), default=None)
    s.add_argument("--verification", choices=sorted(VERIFICATION_STATES), default=None)
    s.add_argument("--evidence", action="append", default=None, help="repeatable evidence JSON object")
    s.add_argument("--source-refs", default=None, help="comma-separated stable source references")
    s.add_argument("--owners", default=None, help="comma-separated owners")
    s.add_argument("--workspace", default=None)
    s.add_argument("--project", default=None)
    s.add_argument("--mission", default=None)
    s.add_argument("--generation", default=None)
    s.add_argument("--actor", default=None)
    s.add_argument("--actor-kind", choices=["human", "agent", "system_tool", "migration_import"], default=None)
    s.add_argument("--role", default=None)
    s.add_argument("--session", default=None)
    s.add_argument("--source", default=None)
    s.add_argument("--attestation", default=None)
    s.add_argument("--provenance-integrity", choices=sorted(PROVENANCE_INTEGRITIES), default=None)
    s.add_argument("--finalize", action="store_true", help="finalize this durable record")
    s.add_argument("--force-finalized", action="store_true", help="administrative recovery: rewrite finalized record and journal it")
    s.add_argument("--phase", choices=["proposed", "executed", "observed", "verified", "canonical"], default="executed")
    s.add_argument("--reason", default=None, help="rationale recorded with every resulting transition")
    s.add_argument("--operation-id", default=None, help="correlate changes belonging to one action")
    s.add_argument("--history-evidence-ref", action="append", default=None)
    s.add_argument("--decision-id", action="append", default=None)
    s.add_argument("--requirement-id", action="append", default=None)
    s.add_argument("--overrides-transition", action="append", default=None)
    s.add_argument("--supersedes-transition", action="append", default=None)
    s.set_defaults(func=cmd_add)

    s = sub.add_parser(
        "scan",
        parents=[common],
        help="list directory files vs graph status (new/pending/indexed)",
    )
    s.add_argument("directory")
    s.add_argument("--glob", default=None, help="optional glob, e.g. '**/*.md'")
    s.add_argument(
        "--types",
        default=None,
        help="comma-separated types (default: document,image,video,audio)",
    )
    s.add_argument("--max-files", type=int, default=5000)
    s.set_defaults(func=cmd_scan)

    s = sub.add_parser(
        "ingest",
        parents=[common],
        help=(
            "stub all docs/images/video/audio in a directory for deep "
            "Cursor LLM ingest (media must be understood, not path-only)"
        ),
    )
    s.add_argument("directory")
    s.add_argument("--glob", default=None)
    s.add_argument("--types", default=None)
    s.add_argument("--max-files", type=int, default=5000)
    s.add_argument(
        "--no-stubs",
        action="store_true",
        help="only report pending/new files; do not create nodes",
    )
    _add_mutation_context_args(s)
    _add_mutation_history_args(s)
    s.set_defaults(func=cmd_ingest)

    s = sub.add_parser(
        "link",
        parents=[common],
        help="link two nodes with a relation (--rel)",
    )
    s.add_argument("frm", metavar="FROM")
    s.add_argument("to", metavar="TO")
    s.add_argument("--rel", required=True)
    s.add_argument("--note", default=None)
    _add_mutation_context_args(s)
    _add_mutation_history_args(s)
    s.set_defaults(func=cmd_link)

    s = sub.add_parser(
        "get",
        parents=[common],
        help="show one node and its adjacent edges",
    )
    s.add_argument("id")
    s.set_defaults(func=cmd_get)

    s = sub.add_parser(
        "search",
        parents=[common],
        help="search nodes (semantic default; lexical/hybrid modes)",
    )
    s.add_argument("query")
    s.add_argument(
        "--mode",
        default="semantic",
        choices=["semantic", "lexical", "hybrid"],
    )
    s.add_argument("--type", default=None)
    s.add_argument("--tag", default=None)
    s.add_argument("--kind", default=None, help="comma-separated graph kind filter")
    s.add_argument(
        "--status",
        default=None,
        help="comma-separated truth status filter",
    )
    s.add_argument(
        "--stage",
        default=None,
        help="comma-separated lifecycle stage filter",
    )
    s.add_argument(
        "--verification",
        default=None,
        choices=sorted(
            {
                "unverified",
                "partially_verified",
                "verified",
                "failed",
                "not_applicable",
            }
        ),
    )
    s.add_argument("--workflow-state", default=None, choices=sorted(WORKFLOW_STATES))
    s.add_argument("--project", default=None)
    s.add_argument("--mission", default=None)
    s.add_argument("--generation", default=None)
    s.add_argument("--actor", default=None)
    s.add_argument("--role", default=None)
    s.add_argument("--as-of", default=None, help="ISO-8601 upper bound on creation time")
    s.add_argument(
        "--exclude-superseded",
        action="store_true",
        help="omit superseded/rejected/deprecated nodes",
    )
    s.add_argument(
        "--current-only",
        action="store_true",
        help="only current, canonical_spec, or proposed nodes",
    )
    s.add_argument(
        "--no-truth-rank",
        action="store_true",
        help="disable truth-aware re-ranking",
    )
    s.add_argument(
        "--explain-ranking",
        action="store_true",
        help="include ranking explanation in JSON output",
    )
    s.add_argument("--include-history", action="store_true", help="history is included by default; explicit for agent callers")
    s.add_argument("--include-superseded", action="store_true", help="superseded nodes are included by default")
    s.add_argument("--limit", type=int, default=10)
    s.set_defaults(func=cmd_search)

    s = sub.add_parser(
        "neighbors",
        parents=[common],
        help="list nearby nodes via BFS (--depth, max 3)",
    )
    s.add_argument("id")
    s.add_argument("--depth", type=int, default=1)
    s.set_defaults(func=cmd_neighbors)

    s = sub.add_parser(
        "path",
        parents=[common],
        help="shortest path between two node ids",
    )
    s.add_argument("a")
    s.add_argument("b")
    s.set_defaults(func=cmd_path)

    s = sub.add_parser(
        "list",
        parents=[common],
        help="list nodes (optional --type / --tag filters)",
    )
    s.add_argument("--type", default=None)
    s.add_argument("--tag", default=None)
    s.set_defaults(func=cmd_list)

    s = sub.add_parser(
        "rm",
        parents=[common],
        help="remove a node and its edges (and vector)",
    )
    s.add_argument("id")
    _add_mutation_context_args(s)
    _add_mutation_history_args(s)
    s.set_defaults(func=cmd_rm)

    s = sub.add_parser(
        "reindex",
        parents=[common],
        help="rebuild embedding vectors for all nodes",
    )
    s.set_defaults(func=cmd_reindex)

    s = sub.add_parser(
        "export",
        parents=[common],
        help="dump graph as JSON or Mermaid (-o to write a file)",
    )
    s.add_argument(
        "--format",
        default="json",
        choices=["json", "mermaid"],
    )
    s.add_argument(
        "-o",
        "--output",
        default=None,
        help="write to file instead of stdout",
    )
    s.set_defaults(func=cmd_export)

    s = sub.add_parser(
        "pack",
        parents=[common],
        help="export a portable pack file to transplant this graph",
    )
    s.add_argument("output", help="output pack path")
    s.add_argument("--name", default="", help="pack name")
    s.add_argument("--description", default="", help="short description")
    s.add_argument(
        "--no-vectors",
        action="store_true",
        help="omit embedding vectors from the pack",
    )
    s.set_defaults(func=cmd_pack)

    s = sub.add_parser(
        "unpack",
        parents=[common],
        help="import a pack (merge/replace); --codex prepares Codex context",
    )
    s.add_argument("pack", help="path to .grapherpack.json")
    s.add_argument(
        "--mode",
        default="merge",
        choices=["merge", "replace"],
        help="merge into existing graph (default) or replace it",
    )
    s.add_argument(
        "--replace",
        action="store_true",
        help="shorthand for --mode replace",
    )
    s.add_argument(
        "--prefix",
        default="",
        help="prefix all imported node ids (safe merge into a full graph)",
    )
    s.add_argument(
        "--no-vectors",
        action="store_true",
        help="do not import pack vectors",
    )
    s.add_argument(
        "--codex",
        action="store_true",
        help="also write GRAPHER_CONTEXT.md and install Codex AGENTS/skill",
    )
    s.set_defaults(func=cmd_unpack)

    codex = sub.add_parser(
        "codex",
        parents=[common],
        help="Codex install, context dump, and transplant kits",
    )
    codex_sub = codex.add_subparsers(dest="codex_command", required=True)

    c_install = codex_sub.add_parser(
        "install",
        parents=[common],
        help="write AGENTS.md grapher section + ~/.codex/skills/grapher",
    )
    c_install.add_argument(
        "--force",
        action="store_true",
        help="overwrite existing Codex skill file",
    )
    c_install.set_defaults(func=cmd_codex_install)

    c_status = codex_sub.add_parser(
        "status",
        parents=[common],
        help="check Codex grapher integration",
    )
    c_status.set_defaults(func=cmd_codex_status)

    c_ctx = codex_sub.add_parser(
        "context",
        parents=[common],
        help="render full-fidelity markdown context for Codex",
    )
    c_ctx.add_argument(
        "-o",
        "--output",
        default=None,
        help="write markdown to file (default: print)",
    )
    c_ctx.add_argument(
        "--from",
        dest="from_pack",
        default=None,
        help="render from a pack file instead of the live graph",
    )
    c_ctx.add_argument("--name", default="")
    c_ctx.add_argument("--description", default="")
    c_ctx.set_defaults(func=cmd_codex_context)

    c_export = codex_sub.add_parser(
        "export",
        parents=[common],
        help="write a Codex transplant kit directory",
    )
    c_export.add_argument("directory", help="output directory for the kit")
    c_export.add_argument("--name", default="")
    c_export.add_argument("--description", default="")
    c_export.add_argument(
        "--no-vectors",
        action="store_true",
        help="omit embedding vectors from the pack",
    )
    c_export.set_defaults(func=cmd_codex_export)

    c_recv = codex_sub.add_parser(
        "receive",
        parents=[common],
        help="unpack a kit/pack and prepare Codex context + AGENTS.md",
    )
    c_recv.add_argument(
        "source",
        help="kit directory or .grapherpack.json path",
    )
    c_recv.add_argument(
        "--mode",
        default="merge",
        choices=["merge", "replace"],
    )
    c_recv.add_argument("--replace", action="store_true")
    c_recv.add_argument("--prefix", default="")
    c_recv.add_argument("--no-vectors", action="store_true")
    c_recv.add_argument(
        "--force",
        action="store_true",
        help="overwrite Codex skill on install",
    )
    c_recv.set_defaults(func=cmd_codex_receive)

    s = sub.add_parser(
        "validate",
        parents=[common],
        help="validate graph schema, ids, edges, and supersession consistency",
    )
    s.set_defaults(func=cmd_validate)

    s = sub.add_parser(
        "audit",
        parents=[common],
        help="health report: type/status/relation distribution and issues",
    )
    s.set_defaults(func=cmd_audit)

    s = sub.add_parser(
        "history", parents=[common],
        help="query immutable state transitions without reconstructing current state",
    )
    s.add_argument("--entity", default=None, help="affected node/entity id")
    s.add_argument("--operation", default=None, help="correlation/operation id")
    s.add_argument("--event-type", default=None, help="transition type")
    s.add_argument("--limit", type=int, default=100)
    s.set_defaults(func=cmd_history)

    migrate = sub.add_parser(
        "migrate",
        parents=[common],
        help="schema migration, inference preview/apply, reset truth metadata",
    )
    migrate_sub = migrate.add_subparsers(dest="migrate_command")

    m_run = migrate_sub.add_parser(
        "run",
        parents=[common],
        help="migrate v1 → v2 schema (default migrate behavior)",
    )
    m_run.add_argument("--to", type=int, default=2, help="target schema version")
    m_run.add_argument("--dry-run", action="store_true", help="preview without writing")
    m_run.add_argument(
        "--infer",
        action="store_true",
        help="include inference preview (requires --approve-infer to apply)",
    )
    m_run.add_argument(
        "--approve-infer",
        action="store_true",
        help="apply inference during migration (requires --infer; preview with --dry-run first)",
    )
    m_run.add_argument(
        "--only-high-confidence",
        action="store_true",
        help="apply only high-confidence status/edge inferences",
    )
    m_run.add_argument(
        "--yes",
        action="store_true",
        help="confirm migration (required unless --dry-run)",
    )
    m_run.add_argument("--domain", default=None)
    m_run.add_argument("--kind", action="append", default=None)
    m_run.add_argument("--stage", action="append", default=None)
    m_run.add_argument("--profile", default=None)
    m_run.add_argument("--name", default=None)
    m_run.add_argument("--no-backup", action="store_true", help="skip migration backup")
    m_run.set_defaults(func=cmd_migrate)

    # Back-compat: `grapher migrate` without subcommand = run
    migrate.add_argument("--to", type=int, default=2, help=argparse.SUPPRESS)
    migrate.add_argument("--dry-run", action="store_true", help=argparse.SUPPRESS)
    migrate.add_argument("--infer", action="store_true", help=argparse.SUPPRESS)
    migrate.add_argument("--approve-infer", action="store_true", help=argparse.SUPPRESS)
    migrate.add_argument("--only-high-confidence", action="store_true", help=argparse.SUPPRESS)
    migrate.add_argument("--yes", action="store_true", help=argparse.SUPPRESS)
    migrate.add_argument("--domain", default=None, help=argparse.SUPPRESS)
    migrate.add_argument("--kind", action="append", default=None, help=argparse.SUPPRESS)
    migrate.add_argument("--stage", action="append", default=None, help=argparse.SUPPRESS)
    migrate.add_argument("--profile", default=None, help=argparse.SUPPRESS)
    migrate.add_argument("--name", default=None, help=argparse.SUPPRESS)
    migrate.add_argument("--no-backup", action="store_true", help=argparse.SUPPRESS)
    migrate.set_defaults(func=cmd_migrate, migrate_command=None)

    m_preview = migrate_sub.add_parser(
        "infer-preview",
        parents=[common],
        help="preview truth/stage/edge inference with explanations (no writes)",
    )
    m_preview.set_defaults(func=cmd_migrate, migrate_command="infer-preview")

    m_apply = migrate_sub.add_parser(
        "infer-apply",
        parents=[common],
        help="apply previewed inference (--yes required)",
    )
    m_apply.add_argument("--dry-run", action="store_true")
    m_apply.add_argument("--yes", action="store_true")
    m_apply.add_argument(
        "--only-high-confidence",
        action="store_true",
        help="apply only high-confidence inferences (status + supersedes edges)",
    )
    m_apply.set_defaults(func=cmd_migrate, migrate_command="infer-apply")

    m_reset = migrate_sub.add_parser(
        "reset-truth",
        parents=[common],
        help="strip inferred status/stage/verification back to unclassified defaults",
    )
    m_reset.add_argument("--dry-run", action="store_true")
    m_reset.add_argument("--yes", action="store_true")
    m_reset.set_defaults(func=cmd_migrate, migrate_command="reset-truth")

    curate_common = argparse.ArgumentParser(add_help=False)
    curate_common.add_argument(
        "--dry-run",
        action="store_true",
        help="preview changes without writing",
    )

    curate = sub.add_parser(
        "curate",
        parents=[common],
        help="truth curation: status, relations, supersession, merge",
    )
    curate_sub = curate.add_subparsers(dest="curate_command", required=True)

    c_status = curate_sub.add_parser(
        "status", parents=[common, curate_common], help="set node truth status"
    )
    c_status.add_argument("id")
    c_status.add_argument("status", choices=sorted(TRUTH_STATUSES))
    _add_mutation_context_args(c_status)
    _add_mutation_history_args(c_status)
    c_status.set_defaults(func=cmd_curate)

    c_relate = curate_sub.add_parser(
        "relate", parents=[common, curate_common], help="add a relation edge"
    )
    c_relate.add_argument("frm", metavar="FROM")
    c_relate.add_argument("to", metavar="TO")
    c_relate.add_argument("--rel", required=True)
    c_relate.add_argument("--note", default=None)
    _add_mutation_context_args(c_relate)
    _add_mutation_history_args(c_relate)
    c_relate.set_defaults(func=cmd_curate)

    c_sup = curate_sub.add_parser(
        "supersede",
        parents=[common, curate_common],
        help="mark old node superseded and link new -supersedes-> old",
    )
    c_sup.add_argument("new_id")
    c_sup.add_argument("old_id")
    c_sup.add_argument("--note", default=None)
    _add_mutation_context_args(c_sup)
    _add_mutation_history_args(c_sup)
    c_sup.set_defaults(func=cmd_curate)

    c_merge = curate_sub.add_parser(
        "merge",
        parents=[common, curate_common],
        help="merge drop node into keep node and rewire edges",
    )
    c_merge.add_argument("keep")
    c_merge.add_argument("drop")
    _add_mutation_context_args(c_merge)
    _add_mutation_history_args(c_merge)
    c_merge.set_defaults(func=cmd_curate)

    c_compact = curate_sub.add_parser(
        "compact",
        parents=[common, curate_common],
        help="suggest replacing duplicate related edges with precise relations",
    )
    c_compact.add_argument("--topic", default=None, help="bounded topic query")
    c_compact.add_argument("--limit", type=int, default=50)
    _add_mutation_context_args(c_compact)
    _add_mutation_history_args(c_compact)
    c_compact.set_defaults(func=cmd_curate)

    c_finalize = curate_sub.add_parser(
        "finalize", parents=[common, curate_common], help="finalize a durable record"
    )
    c_finalize.add_argument("id")
    _add_mutation_context_args(c_finalize)
    _add_mutation_history_args(c_finalize)
    c_finalize.set_defaults(func=cmd_curate)

    c_provenance = curate_sub.add_parser(
        "provenance", parents=[common, curate_common], help="curate provenance integrity"
    )
    c_provenance.add_argument("id")
    c_provenance.add_argument("integrity", choices=sorted(PROVENANCE_INTEGRITIES))
    c_provenance.add_argument("--reason", default=None)
    c_provenance.add_argument("--attestation", default=None)
    _add_mutation_context_args(c_provenance)
    _add_mutation_history_args(c_provenance, include_reason=False)
    c_provenance.set_defaults(func=cmd_curate)

    c_alias = curate_sub.add_parser(
        "alias-rels",
        parents=[common, curate_common],
        help="normalize custom relation labels to canonical registry relations",
    )
    _add_mutation_context_args(c_alias)
    _add_mutation_history_args(c_alias)
    c_alias.set_defaults(func=cmd_curate)

    c_cassio = curate_sub.add_parser(
        "cassio",
        parents=[common, curate_common],
        help="apply CASSIO acceptance curation (truth fixes, checkpoints, repairs)",
    )
    _add_mutation_context_args(c_cassio)
    _add_mutation_history_args(c_cassio)
    c_cassio.set_defaults(func=cmd_curate)

    ck_common = argparse.ArgumentParser(add_help=False)
    ck_common.add_argument("--dry-run", action="store_true")

    ck = sub.add_parser(
        "checkpoint",
        parents=[common],
        help="create or refresh consolidated checkpoint snapshots",
    )
    ck_sub = ck.add_subparsers(dest="checkpoint_command", required=True)

    ck_create = ck_sub.add_parser(
        "create", parents=[common, ck_common], help="create checkpoint node"
    )
    ck_create.add_argument("--title", required=True)
    ck_create.add_argument("--content", default="")
    ck_create.add_argument(
        "--nodes",
        default=None,
        help="comma-separated node ids to derive from (default: all)",
    )
    ck_create.add_argument(
        "--status",
        default="current",
        choices=sorted(TRUTH_STATUSES),
    )
    _add_mutation_context_args(ck_create)
    _add_mutation_history_args(ck_create)
    ck_create.set_defaults(func=cmd_checkpoint)

    ck_refresh = ck_sub.add_parser(
        "refresh", parents=[common, ck_common], help="refresh checkpoint snapshot"
    )
    ck_refresh.add_argument("id")
    ck_refresh.add_argument("--yes", action="store_true", help="apply reviewed refresh")
    _add_mutation_context_args(ck_refresh)
    _add_mutation_history_args(ck_refresh)
    ck_refresh.set_defaults(func=cmd_checkpoint)

    ck_list = ck_sub.add_parser("list", parents=[common], help="list checkpoint snapshots")
    ck_list.set_defaults(func=cmd_checkpoint)

    infer_links_common = argparse.ArgumentParser(add_help=False)
    infer_links_common.add_argument(
        "--dry-run",
        action="store_true",
        help="preview inferred links without writing",
    )
    infer_links = sub.add_parser(
        "infer-links",
        parents=[common, infer_links_common],
        help="infer part_of edges from component_link_rules in config",
    )
    _add_mutation_context_args(infer_links)
    _add_mutation_history_args(infer_links)
    infer_links.set_defaults(func=cmd_infer_links)

    s = sub.add_parser(
        "stat",
        parents=[common],
        help="show node/edge counts and vector index coverage",
    )
    s.set_defaults(func=cmd_stat)

    s = sub.add_parser(
        "dash",
        parents=[common],
        help="open the interactive 3D Plotly/Dash graph dashboard",
    )
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8050)
    s.add_argument(
        "--open",
        action="store_true",
        help="open the dashboard URL in a browser",
    )
    s.add_argument(
        "--debug",
        action="store_true",
        help="run Dash in debug mode",
    )
    s.add_argument(
        "--view",
        default="knowledge",
        choices=[
            "knowledge",
            "lifecycle",
            "dependency",
            "decision",
            "roadmap",
            "current",
            "history",
            "operations",
            "provenance",
        ],
        help="view mode preset (default: knowledge)",
    )
    s.set_defaults(func=cmd_dash)

    return p


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
