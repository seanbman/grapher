"""Map custom relation names to built-in equivalents."""

from __future__ import annotations

from typing import Any

# Common agent-hub / ad-hoc relation aliases → builtin
DEFAULT_RELATION_ALIASES: dict[str, str] = {
    "informs": "references",
    "documents": "references",
    "governed_by": "constrains",
    "contains": "part_of",
    "verifies": "verified_by",
    "documents_implementation": "implements",
    "belongs_to": "part_of",
    "member_of": "part_of",
    "supports": "evidenced_by",
    "describes": "depicts",
}


def alias_relations(
    graph: dict[str, Any],
    aliases: dict[str, str] | None = None,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    mapping = dict(DEFAULT_RELATION_ALIASES)
    if aliases:
        mapping.update(aliases)

    changes: list[dict[str, Any]] = []
    for edge in graph.get("edges") or []:
        rel = edge.get("rel")
        if rel not in mapping:
            continue
        new_rel = mapping[rel]
        changes.append(
            {
                "from": edge.get("from"),
                "to": edge.get("to"),
                "before": rel,
                "after": new_rel,
            }
        )
        if not dry_run:
            edge["rel"] = new_rel

    return {
        "action": "alias_relations",
        "dry_run": dry_run,
        "count": len(changes),
        "changes": changes[:100],
    }
