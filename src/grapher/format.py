"""Human-friendly console formatting for grapher CLI output."""

from __future__ import annotations

import json
import sys
from typing import Any


def _truncate(text: str, width: int = 88) -> str:
    text = " ".join(text.split())
    if len(text) <= width:
        return text
    return text[: width - 1] + "…"


def _print_node(node: dict[str, Any], *, indent: str = "") -> None:
    title = node.get("title") or "(untitled)"
    ntype = node.get("type") or "?"
    nid = node.get("id") or "?"
    print(f"{indent}{title}")
    print(f"{indent}  id: {nid}  type: {ntype}")
    if node.get("path"):
        print(f"{indent}  path: {node['path']}")
    tags = node.get("tags") or []
    if tags:
        print(f"{indent}  tags: {', '.join(str(t) for t in tags)}")
    meta = node.get("meta") or {}
    if meta.get("status"):
        print(f"{indent}  status: {meta['status']}")
    content = (node.get("content") or "").strip()
    if content:
        for line in content.splitlines() or [content]:
            print(f"{indent}  {line}")


def _print_edge(edge: dict[str, Any], *, indent: str = "  ") -> None:
    note = f"  ({edge['note']})" if edge.get("note") else ""
    print(
        f"{indent}{edge.get('from')} --{edge.get('rel')}--> {edge.get('to')}{note}"
    )


def format_human(data: Any) -> bool:
    """Print a human view of data. Returns True if handled, False to fall back."""
    if not isinstance(data, dict):
        return False

    # get: node + edges
    if "node" in data and "edges" in data and "id" in (data.get("node") or {}):
        _print_node(data["node"])
        edges = data.get("edges") or []
        if edges:
            print("edges:")
            for e in edges:
                _print_edge(e)
        else:
            print("edges: (none)")
        return True

    # edge only (link)
    if (
        "from" in data
        and "to" in data
        and "rel" in data
        and "nodes" not in data
        and "node" not in data
    ):
        print("linked")
        _print_edge(data, indent="")
        return True

    # bare node (add)
    if (
        "id" in data
        and "type" in data
        and "title" in data
        and "nodes" not in data
        and "results" not in data
        and "graph" not in data
    ):
        print("saved")
        _print_node(data)
        return True

    # search
    if "results" in data and isinstance(data["results"], list):
        query = data.get("query")
        mode = data.get("mode")
        header = "search"
        if query:
            header += f"  “{query}”"
        if mode:
            header += f"  [{mode}]"
        print(header)
        results = data["results"]
        if not results:
            print("  (no hits)")
            return True
        for i, hit in enumerate(results, 1):
            node = hit.get("node") or {}
            score = hit.get("score")
            score_s = f"{float(score):.3f}" if score is not None else "—"
            print(
                f"  {i}. {score_s}  [{node.get('type')}]  "
                f"{node.get('title')}  ({node.get('id')})"
            )
            content = (node.get("content") or "").strip()
            if content:
                print(f"      {_truncate(content)}")
        return True

    # list
    if "nodes" in data and "count" in data and "edges" not in data:
        nodes = data["nodes"] or []
        print(f"nodes ({data['count']})")
        if not nodes:
            print("  (empty)")
            return True
        for node in nodes:
            tags = ", ".join(node.get("tags") or []) or "—"
            path = node.get("path") or "—"
            print(
                f"  [{node.get('type')}]  {node.get('title')}  "
                f"({node.get('id')})"
            )
            print(f"      path: {path}  tags: {tags}")
        return True

    # neighbors
    if "root" in data and "distances" in data and "nodes" in data:
        print(f"neighbors of {data['root']}  (depth {data.get('depth', 1)})")
        distances = data.get("distances") or {}
        nodes = data.get("nodes") or {}
        ordered = sorted(distances.items(), key=lambda kv: (kv[1], kv[0]))
        for nid, dist in ordered:
            node = nodes.get(nid) or {"id": nid, "title": nid, "type": "?"}
            mark = "●" if dist == 0 else "○"
            print(
                f"  {mark} d={dist}  [{node.get('type')}]  "
                f"{node.get('title')}  ({nid})"
            )
        edges = data.get("edges") or []
        if edges:
            print("edges:")
            for e in edges:
                _print_edge(e)
        return True

    # path
    if "from" in data and "to" in data and "nodes" in data and isinstance(
        data["nodes"], list
    ):
        if data.get("found") is False or not data["nodes"]:
            print(f"no path  {data['from']} → {data['to']}")
            return True
        print(f"path  {data['from']} → {data['to']}")
        print("  " + " → ".join(data["nodes"]))
        for e in data.get("edges") or []:
            _print_edge(e)
        return True

    # init
    if "graph" in data and "vectors" in data and "created" in data:
        print("initialized")
        print(f"  graph:   {data['graph']}")
        print(f"  vectors: {data['vectors']}")
        if data.get("next"):
            print(f"  next:    {data['next']}")
        return True

    # cursor install
    if "files" in data and "project_root" in data and "message" in data:
        print(data.get("message") or "Cursor integration installed")
        print(f"  project: {data['project_root']}")
        print(f"  graph:   {data.get('graph')}")
        for path, status in (data.get("files") or {}).items():
            print(f"  {status:10}  {path}")
        if data.get("hint"):
            print(f"  note: {data['hint']}")
        return True

    # cursor status
    if "rule_installed" in data and "skill_installed" in data:
        ready = "ready" if data.get("ready") else "not ready"
        print(f"cursor integration: {ready}")
        print(f"  project:  {data.get('project_root')}")
        print(f"  graph:    {'yes' if data.get('graph_initialized') else 'no'}")
        print(f"  rule:     {'yes' if data.get('rule_installed') else 'no'}  ({data.get('rule_path')})")
        print(f"  skill:    {'yes' if data.get('skill_installed') else 'no'}  ({data.get('skill_path')})")
        return True

    # scan
    if "files" in data and "counts" in data and "directory" in data:
        counts = data["counts"]
        print(f"scan  {data['directory']}")
        print(
            f"  new {counts.get('new', 0)}  "
            f"pending {counts.get('pending', 0)}  "
            f"indexed {counts.get('indexed', 0)}  "
            f"skipped {counts.get('skipped_other', 0)}"
        )
        for f in data.get("files") or []:
            print(
                f"  [{f.get('status'):7}]  [{f.get('type')}]  "
                f"{f.get('path')}"
                + (f"  ({f.get('node_id')})" if f.get("node_id") else "")
            )
        return True

    # ingest
    if "pending" in data and "instruction" in data:
        print(f"ingest  {data.get('directory')}")
        print(
            f"  stubs created: {data.get('created_stubs', 0)}  "
            f"pending: {data.get('pending_count', 0)}  "
            f"already indexed: {data.get('indexed_skipped', 0)}"
        )
        pending = data.get("pending") or []
        if not pending:
            print("  (nothing pending)")
        else:
            print("  pending for LLM enrichment:")
            for p in pending:
                print(
                    f"    [{p.get('type')}]  {p.get('path')}  "
                    f"id={p.get('node_id') or '(none)'}"
                )
                if p.get("abs_path") and p.get("abs_path") != p.get("path"):
                    print(f"         abs: {p['abs_path']}")
        print()
        print("  FULL INGEST REQUIRED — Cursor is the enriching LLM.")
        print("  Deeply consume + understand EVERY pending file, then graph that understanding.")
        print("  Images/video/audio: NOT path-only. Vision / watch / listen — write what you learned.")
        print("  next:")
        print(
            "    grapher add --id <id> --type <type> --title <title> "
            "--path <path> --content \"<deep summary>\""
        )
        print("  done when: grapher scan <DIR> shows pending 0")
        return True

    # reindex
    if "indexed" in data and "model" in data and "provider" in data:
        print("reindexed")
        print(f"  indexed: {data['indexed']}  skipped empty: {data.get('skipped_empty', 0)}")
        print(f"  model:   {data['provider']} / {data['model']}  dims={data.get('dims')}")
        if data.get("path"):
            print(f"  file:    {data['path']}")
        return True

    # stat
    if "by_type" in data and "nodes" in data and isinstance(data["nodes"], int):
        print(f"graph  {data['nodes']} nodes  {data.get('edges', 0)} edges")
        if data.get("by_type"):
            parts = [f"{k}={v}" for k, v in data["by_type"].items()]
            print(f"  types:  {', '.join(parts)}")
        if data.get("by_rel"):
            parts = [f"{k}={v}" for k, v in data["by_rel"].items()]
            print(f"  rels:   {', '.join(parts)}")
        vec = data.get("vectors")
        if vec:
            print(
                f"  vectors: {vec.get('coverage')}/{vec.get('nodes')} covered  "
                f"({vec.get('provider')}/{vec.get('model')}, dims={vec.get('dims')})"
            )
        return True

    # rm
    if set(data.keys()) == {"removed"} or (
        "removed" in data and len(data) <= 2
    ):
        print(f"removed  {data['removed']}")
        return True

    # pack
    if data.get("action") == "pack":
        print(f"packed  {data.get('name') or 'untitled'}")
        print(f"  file:    {data.get('path')}")
        if data.get("description"):
            print(f"  about:   {data['description']}")
        print(
            f"  nodes:   {data.get('nodes', 0)}  "
            f"edges: {data.get('edges', 0)}  "
            f"vectors: {data.get('vectors', 0)}"
        )
        if data.get("exported_at"):
            print(f"  at:      {data['exported_at']}")
        return True

    # unpack
    if data.get("action") == "unpack":
        print(f"unpacked  {data.get('name') or 'pack'}  [{data.get('mode')}]")
        print(f"  pack:    {data.get('pack')}")
        print(f"  graph:   {data.get('graph')}")
        if data.get("prefix"):
            print(f"  prefix:  {data['prefix']}")
        print(
            f"  added:   nodes={data.get('nodes_added', 0)}  "
            f"updated={data.get('nodes_updated', 0)}  "
            f"edges={data.get('edges_added', 0)}"
        )
        print(
            f"  totals:  nodes={data.get('nodes', 0)}  "
            f"edges={data.get('edges', 0)}  "
            f"vectors_imported={data.get('vectors', 0)}"
        )
        if data.get("hint"):
            print(f"  note:    {data['hint']}")
        return True

    # codex install
    if data.get("action") == "codex_install":
        print(data.get("message") or "Codex integration installed")
        print(f"  project: {data.get('project_root')}")
        print(f"  AGENTS:  {data.get('agents_status')}  ({data.get('agents_md')})")
        skill = data.get("skill") or {}
        print(f"  skill:   {skill.get('status')}  ({skill.get('path')})")
        print(
            f"  context: {'yes' if data.get('context_present') else 'no'}  "
            f"({data.get('context_path')})"
        )
        return True

    # codex status
    if data.get("action") == "codex_status":
        ready = "ready" if data.get("ready") else "not ready"
        print(f"codex integration: {ready}")
        print(f"  project:  {data.get('project_root')}")
        print(f"  graph:    {'yes' if data.get('graph_initialized') else 'no'}")
        print(f"  AGENTS:   {'yes' if data.get('agents_section') else 'no'}  ({data.get('agents_path')})")
        print(f"  skill:    {'yes' if data.get('skill_installed') else 'no'}  ({data.get('skill_path')})")
        print(f"  context:  {'yes' if data.get('context_present') else 'no'}  ({data.get('context_path')})")
        return True

    # codex context
    if data.get("action") == "codex_context":
        print(f"context  {data.get('name') or 'untitled'}")
        print(
            f"  nodes: {data.get('nodes', 0)}  edges: {data.get('edges', 0)}  "
            f"chars: {data.get('chars', 0)}"
        )
        if data.get("path"):
            print(f"  file:  {data['path']}")
        elif data.get("markdown"):
            print()
            print(data["markdown"])
        return True

    # codex export
    if data.get("action") == "codex_export":
        print(f"codex export  {data.get('name') or 'kit'}")
        print(f"  dir:     {data.get('directory')}")
        print(f"  pack:    {data.get('pack')}")
        print(f"  context: {data.get('context')}")
        print(
            f"  nodes:   {data.get('nodes', 0)}  edges: {data.get('edges', 0)}  "
            f"vectors: {data.get('vectors', 0)}"
        )
        if data.get("message"):
            print(f"  next:    {data['message']}")
        return True

    # codex receive
    if data.get("action") == "codex_receive":
        print(data.get("message") or "Received for Codex")
        print(f"  project: {data.get('project_root')}")
        print(f"  pack:    {data.get('pack')}")
        print(f"  context: {data.get('context')}  ({data.get('context_source')})")
        un = data.get("unpack") or {}
        print(
            f"  unpack:  mode={un.get('mode')}  "
            f"nodes+={un.get('nodes_added', 0)}  "
            f"edges+={un.get('edges_added', 0)}"
        )
        inst = data.get("install") or {}
        print(f"  AGENTS:  {inst.get('agents_status')}")
        skill = inst.get("skill") or {}
        print(f"  skill:   {skill.get('status')}")
        if data.get("hint"):
            print(f"  note:    {data['hint']}")
        return True

    # export full graph as human summary
    if "version" in data and "nodes" in data and "edges" in data:
        nodes = data["nodes"]
        if isinstance(nodes, dict):
            print(f"graph export  {len(nodes)} nodes  {len(data.get('edges') or [])} edges")
            for node in nodes.values():
                print(
                    f"  [{node.get('type')}]  {node.get('title')}  ({node.get('id')})"
                )
            for e in data.get("edges") or []:
                _print_edge(e)
            return True

    return False


def emit(data: Any, *, as_json: bool) -> None:
    if as_json:
        json.dump(data, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return
    if format_human(data):
        return
    # fallback: indented JSON rather than opaque blob
    json.dump(data, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
