"""Built-in registries for graph kinds, lifecycle stages, statuses, relations, and profiles."""

from __future__ import annotations

from typing import Any

# --- Graph kinds (what the graph emphasizes) ---
GRAPH_KINDS: frozenset[str] = frozenset(
    {
        "knowledge",
        "brainstorm",
        "concept",
        "requirements",
        "decision",
        "design",
        "dependency",
        "roadmap",
        "implementation",
        "launch",
        "operations",
        "retrospective",
    }
)

# --- Lifecycle stages (where work sits) ---
LIFECYCLE_STAGES: frozenset[str] = frozenset(
    {
        "ideation",
        "designing",
        "planning",
        "developing",
        "launching",
        "maintaining",
    }
)

# Canonical display / migration order (not JSON insertion order)
CANONICAL_STAGE_ORDER: list[str] = [
    "ideation",
    "designing",
    "planning",
    "developing",
    "launching",
    "maintaining",
]

STAGE_ALIASES: dict[str, str] = {
    "design": "designing",
    "development": "developing",
    "develop": "developing",
    "launch": "launching",
    "maintenance": "maintaining",
    "maintain": "maintaining",
    "plan": "planning",
    "ideate": "ideation",
}

# --- Truth status (how to treat a node as truth) ---
TRUTH_STATUSES: frozenset[str] = frozenset(
    {
        "unclassified",
        "proposed",
        "current",
        "canonical_spec",
        "superseded",
        "historical",
        "rejected",
        "deprecated",
    }
)

STATUS_RANK_WEIGHTS: dict[str, float] = {
    "current": 1.0,
    "canonical_spec": 0.95,
    "proposed": 0.75,
    "historical": 0.6,
    "unclassified": 0.55,
    "superseded": 0.25,
    "deprecated": 0.2,
    "rejected": 0.15,
}

# --- Workflow state ---
WORKFLOW_STATES: frozenset[str] = frozenset(
    {
        "not_started",
        "active",
        "blocked",
        "completed",
        "cancelled",
        "on_hold",
        "not_applicable",
    }
)

# --- Verification ---
VERIFICATION_STATES: frozenset[str] = frozenset(
    {
        "unverified",
        "partially_verified",
        "verified",
        "failed",
        "not_applicable",
    }
)

VERIFICATION_RANK_BOOST: dict[str, float] = {
    "verified": 0.08,
    "partially_verified": 0.04,
    "unverified": 0.0,
    "failed": -0.05,
    "not_applicable": 0.0,
}

# --- Node types (legacy + general work) ---
LEGACY_NODE_TYPES: frozenset[str] = frozenset(
    {
        "document",
        "image",
        "video",
        "audio",
        "instruction",
        "finding",
        "concept",
        "command",
        "session",
        "other",
    }
)

GENERAL_NODE_TYPES: frozenset[str] = frozenset(
    {
        "idea",
        "question",
        "goal",
        "requirement",
        "constraint",
        "assumption",
        "option",
        "decision",
        "component",
        "artifact",
        "person",
        "organization",
        "stakeholder",
        "task",
        "milestone",
        "deliverable",
        "dependency",
        "risk",
        "issue",
        "incident",
        "metric",
        "policy",
        "checkpoint",
        "mission",
        "handoff",
        "acceptance",
        "audit_record",
        "event",
        "claim",
    }
)

BUILTIN_NODE_TYPES: frozenset[str] = LEGACY_NODE_TYPES | GENERAL_NODE_TYPES

# --- Relations ---
LEGACY_RELS: frozenset[str] = frozenset(
    {
        "references",
        "depends_on",
        "discovered_in",
        "applies_to",
        "depicts",
        "related",
    }
)

PRECISE_RELS: frozenset[str] = frozenset(
    {
        "supersedes",
        "implements",
        "deviates_from",
        "fixes",
        "caused_by",
        "blocks",
        "enables",
        "replaces_ui_of",
        "verified_by",
        "evidenced_by",
        "derived_from",
        "decided_by",
        "chosen_over",
        "satisfies",
        "violates",
        "constrains",
        "owns",
        "assigned_to",
        "produces",
        "part_of",
        "precedes",
        "follows",
        "launches",
        "maintains",
        "affects",
        "authored_by",
        "performed_by",
        "observed_by",
        "hands_off",
        "accepts",
        "audits",
        "contradicts",
    }
)

BUILTIN_RELS: frozenset[str] = LEGACY_RELS | PRECISE_RELS

REL_DESCRIPTIONS: dict[str, str] = {
    "related": "Generic association (use only when no precise relation fits)",
    "references": "Points to or cites another node",
    "depicts": "Visual representation of another node",
    "applies_to": "Rule or instruction applies to target",
    "depends_on": "Requires another node",
    "discovered_in": "Finding discovered in context of target",
    "supersedes": "Newer node replaces older node (directed: new -> old)",
    "implements": "Realizes or fulfills a spec/design/requirement",
    "deviates_from": "Intentionally differs from canonical spec",
    "fixes": "Resolves an issue or bug",
    "caused_by": "Effect caused by source",
    "blocks": "Prevents progress on target",
    "enables": "Makes target possible",
    "verified_by": "Claim verified by evidence/test",
    "evidenced_by": "Supported by evidence record",
    "derived_from": "Summarized or consolidated from sources",
    "decided_by": "Decision made by person/group/process",
    "chosen_over": "Selected instead of alternative",
    "satisfies": "Meets a requirement or constraint",
    "violates": "Breaks a requirement or constraint",
    "constrains": "Limits or bounds target",
    "owns": "Owned by person/team",
    "assigned_to": "Work assigned to owner",
    "produces": "Creates or outputs artifact",
    "part_of": "Component of larger whole",
    "precedes": "Comes before in sequence",
    "follows": "Comes after in sequence",
    "launches": "Launch activity for target",
    "maintains": "Ongoing maintenance of target",
    "affects": "Has impact on target",
    "replaces_ui_of": "UI replacement for prior design",
    "authored_by": "Record was authored by actor or session",
    "performed_by": "Action was performed by actor or session",
    "observed_by": "Event or result was observed by actor or session",
    "hands_off": "Transfers work or context to target",
    "accepts": "Acceptance record accepts the target scope",
    "audits": "Audit record examines the target scope",
    "contradicts": "Explicit unresolved disagreement with target",
}

# --- Evidence types ---
EVIDENCE_TYPES: frozenset[str] = frozenset(
    {
        "test",
        "file",
        "document",
        "image",
        "measurement",
        "observation",
        "commit",
        "conversation",
        "external_source",
        "command",
        "command_output",
        "human_observation",
        "agent_report",
        "external_artifact",
        "grapher_state",
        "log",
        "other",
    }
)

# --- Profiles ---
PROFILES: frozenset[str] = frozenset(
    {"general", "software", "product", "research", "campaign", "operations"}
)

PROFILE_DEFAULTS: dict[str, dict[str, Any]] = {
    "general": {
        "domain": "general",
        "kinds": ["knowledge"],
        "stages": list(LIFECYCLE_STAGES),
    },
    "software": {
        "domain": "software",
        "kinds": ["knowledge", "implementation", "decision", "design"],
        "stages": ["designing", "developing", "maintaining"],
    },
    "product": {
        "domain": "product",
        "kinds": ["brainstorm", "design", "roadmap", "launch"],
        "stages": ["ideation", "designing", "planning", "launching"],
    },
    "research": {
        "domain": "research",
        "kinds": ["knowledge", "requirements", "decision"],
        "stages": ["ideation", "planning", "developing", "maintaining"],
    },
    "campaign": {
        "domain": "campaign",
        "kinds": ["brainstorm", "roadmap", "launch", "operations"],
        "stages": ["ideation", "planning", "launching", "maintaining"],
    },
    "operations": {
        "domain": "operations",
        "kinds": ["operations", "knowledge", "retrospective"],
        "stages": ["launching", "maintaining"],
    },
}

# --- Dash view modes ---
VIEW_MODES: frozenset[str] = frozenset(
    {
        "knowledge",
        "lifecycle",
        "dependency",
        "decision",
        "roadmap",
        "current",
        "history",
        "operations",
        "provenance",
    }
)

VIEW_MODE_LABELS: dict[str, str] = {
    "knowledge": "Knowledge Network",
    "lifecycle": "Lifecycle Flow",
    "dependency": "Dependency Graph",
    "decision": "Decision Graph",
    "roadmap": "Roadmap View",
    "current": "Current State",
    "history": "History / Supersession",
    "operations": "Maintenance / Operations",
    "provenance": "Provenance / Mission History",
}

# Relation emphasis per view mode (None = show all edge types)
VIEW_RELATIONS: dict[str, frozenset[str] | None] = {
  # Knowledge network shows every link; other modes emphasize a subset.
    "knowledge": None,
    "lifecycle": frozenset({"precedes", "follows", "part_of", "produces"}),
    "dependency": frozenset(
        {"depends_on", "blocks", "enables", "precedes", "follows", "part_of"}
    ),
    "decision": frozenset(
        {
            "chosen_over",
            "decided_by",
            "supersedes",
            "constrains",
            "satisfies",
            "evidenced_by",
            "derived_from",
        }
    ),
    "roadmap": frozenset(
        {"precedes", "follows", "depends_on", "blocks", "assigned_to", "part_of"}
    ),
    "current": frozenset(
        {"derived_from", "implements", "verified_by", "supersedes", "evidenced_by"}
    ),
    "history": frozenset(
        {
            "supersedes",
            "deviates_from",
            "implements",
            "fixes",
            "caused_by",
            "verified_by",
        }
    ),
    "operations": frozenset(
        {"caused_by", "fixes", "affects", "maintains", "verified_by", "assigned_to"}
    ),
    "provenance": frozenset(
        {"applies_to", "authored_by", "performed_by", "observed_by",
         "hands_off", "accepts", "audits", "supersedes", "contradicts"}
    ),
}

PROVENANCE_INTEGRITIES: frozenset[str] = frozenset(
    {"unknown", "declared", "verified", "contested", "invalidated"}
)


def normalize_stage(raw: str) -> str:
    s = raw.strip().lower()
    return STAGE_ALIASES.get(s, s)


def parse_repeatable(values: list[str] | None) -> list[str]:
    """Parse comma-separated and repeated flag values into unique ordered list."""
    if not values:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for v in values:
        for part in v.split(","):
            part = part.strip()
            if part and part not in seen:
                seen.add(part)
                out.append(part)
    return out


def validate_kinds(kinds: list[str], *, extra: frozenset[str] | None = None) -> list[str]:
    allowed = GRAPH_KINDS | (extra or frozenset())
    bad = [k for k in kinds if k not in allowed]
    if bad:
        raise ValueError(
            f"unknown graph kind(s): {bad}. Allowed: {sorted(allowed)}. "
            "Add custom kinds in .grapher/config.json"
        )
    return kinds


def validate_stages(stages: list[str], *, extra: frozenset[str] | None = None) -> list[str]:
    allowed = LIFECYCLE_STAGES | (extra or frozenset())
    normalized = [normalize_stage(s) for s in stages]
    bad = [s for s in normalized if s not in allowed]
    if bad:
        raise ValueError(
            f"unknown lifecycle stage(s): {bad}. Allowed: {sorted(allowed)}. "
            f"Aliases: {STAGE_ALIASES}"
        )
    return normalized
