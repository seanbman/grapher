# Grapher Canonical Roadmap

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
| M9 | Generalized prompts and Cursor integration | planned |
| M10 | Dash export and approved editing | planned |
| M11 | Acceptance fixtures and tests | planned |
| M12 | Documentation and full-suite completion | planned |

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
