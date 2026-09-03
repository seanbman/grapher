"""Project configuration loader (.grapher/config.json)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from grapher.registry import (
    BUILTIN_NODE_TYPES,
    BUILTIN_RELS,
    GRAPH_KINDS,
    LIFECYCLE_STAGES,
    PROFILE_DEFAULTS,
    PROFILES,
)


def config_path_for(graph_path: Path) -> Path:
    return graph_path.parent / "config.json"


def default_config(*, profile: str = "general") -> dict[str, Any]:
    prof = PROFILE_DEFAULTS.get(profile, PROFILE_DEFAULTS["general"])
    return {
        "profile": profile,
        "domain": prof["domain"],
        "kinds": list(prof["kinds"]),
        "stages": list(prof["stages"]),
        "custom_node_types": [],
        "custom_relations": {},
        "custom_kinds": [],
        "stage_aliases": {},
        "status_rank_weights": {},
        "checkpoint_definitions": [],
        "component_link_rules": [],
        "relation_aliases": {},
    }


def load_config(graph_path: Path | None = None) -> dict[str, Any]:
    if graph_path is None:
        return default_config()
    cpath = config_path_for(graph_path)
    if not cpath.is_file():
        return default_config()
    with cpath.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        return default_config()
    base = default_config(profile=data.get("profile", "general"))
    base.update(data)
    return base


def allowed_node_types(config: dict[str, Any] | None = None) -> frozenset[str]:
    custom = frozenset((config or {}).get("custom_node_types") or [])
    return BUILTIN_NODE_TYPES | custom


def allowed_relations(config: dict[str, Any] | None = None) -> frozenset[str]:
    custom = frozenset((config or {}).get("custom_relations") or {})
    return BUILTIN_RELS | custom


def allowed_kinds(config: dict[str, Any] | None = None) -> frozenset[str]:
    custom = frozenset((config or {}).get("custom_kinds") or [])
    return GRAPH_KINDS | custom


def allowed_stages(config: dict[str, Any] | None = None) -> frozenset[str]:
    return LIFECYCLE_STAGES


def canonical_stage(value: str, config: dict[str, Any] | None = None) -> str:
    from grapher.registry import normalize_stage
    raw = value.strip().lower()
    alias = ((config or {}).get("stage_aliases") or {}).get(raw, raw)
    return normalize_stage(str(alias))


def canonical_relation(value: str, config: dict[str, Any] | None = None) -> str:
    aliases = (config or {}).get("relation_aliases") or {}
    return str(aliases.get(value, value)).strip()


def save_config(graph_path: Path, config: dict[str, Any]) -> None:
    cpath = config_path_for(graph_path)
    cpath.parent.mkdir(parents=True, exist_ok=True)
    cpath.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
