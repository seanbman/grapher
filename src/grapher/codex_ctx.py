"""Render Grapher context for Codex using the generalized agent contract."""

from __future__ import annotations

from typing import Any

from grapher.agent_prompt import render_agent_context


def render_context_markdown(
    graph: dict[str, Any],
    *,
    name: str = "untitled",
    description: str = "",
) -> str:
    return render_agent_context(
        graph,
        name=name,
        description=description,
        consumer="codex",
    )


def render_context_from_pack(pack: dict[str, Any]) -> str:
    meta = pack.get("meta") or {}
    return render_context_markdown(
        pack.get("graph") or {"nodes": {}, "edges": []},
        name=str(meta.get("name") or "untitled"),
        description=str(meta.get("description") or ""),
    )
