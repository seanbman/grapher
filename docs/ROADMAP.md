# Grapher Canonical Roadmap

[Documentation index](INDEX.md) · [Architecture](ARCHITECTURE.md) · [Procedures](PROCEDURES.md)

This document is the authoritative numbered implementation sequence for Grapher. Agents and humans MUST consult it before declaring the "next milestone". Remediation, bug fixes, security work, truth-state hardening, and maintenance do not renumber or displace these milestones unless this roadmap is explicitly revised.

## Milestones

| ID | Milestone | State |
|---|---|---|
| M1 | Architecture and baseline | completed |
| M2 | Registries, normalized models, and v1 reader | completed |
| M3 | v2 serialization and migration | completed |
| M4 | CLI flags | completed |
| M5 | Validation and audit | completed |
| M6 | Truth-aware relations, supersession, and retrieval | completed |
| M7 | Grapher-to-Dash adapter and visualization | completed |
| M8 | Checkpoints and compaction previews | **next** |
| M9 | Generalized prompts and **Codex integration** | planned |
| M10 | **Cursor integration**, Dash export, and approved editing | planned |
| M11 | Acceptance fixtures and tests | planned |
| M12 | Documentation and full-suite completion | planned |

## Integration priority

Codex is the first-class agent integration target. Grapher's generalized agent-facing contracts should be proven with Codex before equivalent Cursor integration is advanced. Cursor support follows Codex and should reuse the stabilized agent-agnostic interfaces rather than defining them.

## State rules

- `completed`: milestone acceptance criteria have been met.
- `next`: the next numbered milestone to advance.
- `planned`: ordered future work.
- Maintenance and remediation are tracked separately from the numbered sequence.
- A milestone state or ordering change requires an explicit roadmap update; it must not be inferred from recent work.

## Current maintenance debt

Truth-state admission hardening was merged after M7. It is maintenance/hardening, not a numbered milestone. Five grandfathered `unclassified` records remain a finite curation queue and do not displace M8.

## Agent rule

Before answering roadmap questions such as "what is next?", agents should consult this file and, where available, the corresponding canonical Grapher roadmap records. Repository state and recent PR chronology are not substitutes for the declared roadmap.

Every substantive Grapher pass must also update versioned `.grapher/shared` self-state. CI enforces this rule; see [PROCEDURES.md](PROCEDURES.md#self-graph-and-ci-procedure).

## Appendix: roadmap procedure flow

```mermaid
flowchart LR
    READ["Consult roadmap\ndocs/ROADMAP.md\ninception: 9917cc8\ncurrent: c96ba65"]
    CLASSIFY["Classify work\nmilestone vs maintenance\ninception: 9917cc8\ncurrent: c96ba65"]
    EXECUTE["Implement scoped pass\nsrc/grapher/*\ninception: 9917cc8\ncurrent: c96ba65"]
    GRAPH["Update Grapher self-state\n.grapher/shared/*\ninception: 9917cc8\ncurrent: c96ba65"]
    CI["CI governance + tests\n.github/workflows/ci.yml\ninception: 9917cc8\ncurrent: c96ba65"]
    ADVANCE["Advance milestone only on accepted completion\ndocs/ROADMAP.md\ninception: 9917cc8\ncurrent: c96ba65"]

    READ --> CLASSIFY --> EXECUTE --> GRAPH --> CI --> ADVANCE
```

Architecture details: [ARCHITECTURE.md](ARCHITECTURE.md). Operating procedure: [PROCEDURES.md](PROCEDURES.md).
