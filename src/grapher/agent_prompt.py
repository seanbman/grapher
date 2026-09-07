"""Model-agnostic agent prompt/context rendering for Grapher consumers."""

from __future__ import annotations

from typing import Any


OPERATING_SEQUENCE = (
    "READ",
    "SEARCH",
    "ACT",
    "RECORD",
    "VALIDATE",
    "PUBLISH",
)


def _node_status(node: dict[str, Any]) -> str:
    return str(node.get("status") or "unclassified")


def render_operating_contract(*, consumer: str = "agent") -> str:
    """Render the shared agent operating contract for integration surfaces."""
    return "\n".join(
        [
            f"Consumer: `{consumer}`.",
            "",
            "1. **READ** Grapher context and repository instructions before making assumptions.",
            "2. **SEARCH** Grapher before rediscovering project state: `grapher search`, `grapher get`, `grapher neighbors`.",
            "3. **ACT** only from retrieved evidence, repository state, and explicit user instructions.",
            "4. **RECORD** durable discoveries, decisions, implementations, tests, and results back into Grapher with explicit truth status and provenance.",
            "5. **VALIDATE** with `grapher validate` and `grapher audit` before publication.",
            "6. **PUBLISH** shared state with `grapher publish`; never treat local runtime state as the shared canonical artifact.",
        ]
    )


def render_agent_context(
    graph: dict[str, Any],
    *,
    name: str = "untitled",
    description: str = "",
    consumer: str = "agent",
) -> str:
    """Render deterministic durable context for an agent consumer.

    The contract is intentionally model-agnostic. Integrations such as Codex
    and Cursor consume this renderer/contract and may wrap it with
    consumer-specific installation behavior, but must not redefine the
    underlying operating sequence.
    """
    nodes = graph.get("nodes") or {}
    edges = graph.get("edges") or []
    ordered = sorted(
        nodes.values(),
        key=lambda node: (
            str(node.get("type") or ""),
            str(node.get("title") or ""),
            str(node.get("id") or ""),
        ),
    )

    lines: list[str] = [
        f"# Grapher context: {name}",
        "",
        f"> Consumer: `{consumer}`. Read this entire document before acting.",
        "> Grapher is durable project state; repository files remain the implementation source.",
        "",
        "## Operating contract",
        *render_operating_contract(consumer=consumer).splitlines()[2:],
        "",
        "## Guardrails",
        "- Keep active context compact; retrieve relevant slices instead of replaying entire histories.",
        "- Do not infer truth status from recency alone.",
        "- Do not overwrite finalized semantic history; use curation/supersession paths.",
        "- Do not cross mission or generation boundaries when consolidating state.",
        "- Paths are references, not understanding; durable media/document meaning belongs in node content.",
        "",
        "## Summary",
        f"- **nodes:** {len(nodes)}",
        f"- **edges:** {len(edges)}",
    ]
    if description:
        lines.append(f"- **description:** {description}")

    lines.extend(["", "## Nodes", ""])
    for node in ordered:
        nid = str(node.get("id") or "?")
        title = str(node.get("title") or nid)
        ntype = str(node.get("type") or "other")
        content = str(node.get("content") or "").strip() or "_(empty — requires enrichment)_"
        scope = node.get("scope") or {}
        lines.append(f"### {title} (`{nid}`) · `{ntype}`")
        lines.append(f"- status: `{_node_status(node)}`")
        lines.append(f"- verification: `{node.get('verification') or 'unverified'}`")
        if scope:
            scope_text = ", ".join(f"{k}={v}" for k, v in sorted(scope.items()) if v)
            if scope_text:
                lines.append(f"- scope: {scope_text}")
        if node.get("path"):
            lines.append(f"- path: `{node['path']}`")
        lines.extend(["", content, ""])

    lines.extend(["## Relationships", ""])
    if not edges:
        lines.append("_No edges._")
    else:
        for edge in sorted(
            edges,
            key=lambda edge: (
                str(edge.get("from") or ""),
                str(edge.get("rel") or ""),
                str(edge.get("to") or ""),
            ),
        ):
            note = f" — {edge['note']}" if edge.get("note") else ""
            lines.append(
                f"- `{edge.get('from')}` --**{edge.get('rel')}**--> `{edge.get('to')}`{note}"
            )

    lines.append("")
    return "\n".join(lines)
