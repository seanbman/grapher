"""Render full-fidelity markdown context for Codex (minimal idea loss)."""

from __future__ import annotations

from typing import Any


def _is_pending(node: dict[str, Any]) -> bool:
    meta = node.get("meta") or {}
    if meta.get("status") == "pending":
        return True
    return not (node.get("content") or "").strip()


def render_context_markdown(
    graph: dict[str, Any],
    *,
    name: str = "untitled",
    description: str = "",
) -> str:
    nodes = graph.get("nodes") or {}
    edges = graph.get("edges") or []
    lines: list[str] = [
        f"# Grapher context: {name}",
        "",
        "> Transplanted idea. **Read this entire document before acting.**",
        "> Then use `grapher search` / `grapher get` for retrieval.",
        "",
        "## Summary",
        f"- **nodes:** {len(nodes)}",
        f"- **edges:** {len(edges)}",
    ]
    if description:
        lines.append(f"- **description:** {description}")
    lines.extend(["", "## Nodes", ""])

    ordered = sorted(
        nodes.values(),
        key=lambda n: (
            str(n.get("type") or ""),
            str(n.get("title") or ""),
            str(n.get("id") or ""),
        ),
    )
    for node in ordered:
        nid = node.get("id") or "?"
        title = node.get("title") or nid
        ntype = node.get("type") or "other"
        path = node.get("path") or "—"
        tags = ", ".join(str(t) for t in (node.get("tags") or [])) or "—"
        status = (node.get("meta") or {}).get("status") or (
            "pending" if _is_pending(node) else "indexed"
        )
        content = (node.get("content") or "").strip() or "_(empty — needs enrichment)_"
        lines.append(f"### {title} (`{nid}`) · `{ntype}`")
        lines.append(f"- path: `{path}`")
        lines.append(f"- tags: {tags}")
        lines.append(f"- status: `{status}`")
        lines.append("")
        lines.append(content)
        lines.append("")

    lines.extend(["## Relationships", ""])
    if not edges:
        lines.append("_No edges._")
    else:
        for e in edges:
            note = f"  — {e['note']}" if e.get("note") else ""
            lines.append(
                f"- `{e.get('from')}` --**{e.get('rel')}**--> `{e.get('to')}`{note}"
            )
    lines.extend(
        [
            "",
            "## Codex operating rules",
            "1. Treat this document as source of truth for the transplanted idea.",
            "2. Do **not** discard media/image/video/audio understanding buried in node content — paths alone are not knowledge.",
            "3. After reading, prefer `grapher search \"<question>\"` / `grapher get <id>` over rediscovering.",
            "4. Persist new durable facts with `grapher add` / `grapher link`.",
            "",
        ]
    )
    return "\n".join(lines)


def render_context_from_pack(pack: dict[str, Any]) -> str:
    meta = pack.get("meta") or {}
    return render_context_markdown(
        pack.get("graph") or {"nodes": {}, "edges": []},
        name=str(meta.get("name") or "untitled"),
        description=str(meta.get("description") or ""),
    )
