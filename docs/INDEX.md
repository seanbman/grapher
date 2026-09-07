# Grapher Documentation Index

This is the canonical entry point for Grapher documentation. Human and agent readers should start here, then follow the topic links below.

## Core navigation

| Topic | Document | Purpose |
|---|---|---|
| Architecture | [ARCHITECTURE.md](ARCHITECTURE.md) | System boundaries, canonical state, mutation path, transport, Dash, and agent integrations |
| Procedures | [PROCEDURES.md](PROCEDURES.md) | Change procedure, self-graph publication, CI gates, checkpoints, compaction, and release flow |
| Roadmap | [ROADMAP.md](ROADMAP.md) | Canonical M1-M12 implementation order and integration priority |
| Codex integration | [CODEX_INTEGRATION.md](CODEX_INTEGRATION.md) | M9 generalized agent contract and Codex-first integration procedure |
| Cursor + Dash editing | [M10_CURSOR_DASH_EDITING.md](M10_CURSOR_DASH_EDITING.md) | M10 shared Cursor contract plus proposal-first, approval-gated Dash editing architecture |
| Git transport | [GIT_TRANSPORT.md](GIT_TRANSPORT.md) | Publish/sync boundary for local and Git-shared graph state |
| Semantic entry schema | [SEMANTIC_ENTRY_SCHEMA.md](SEMANTIC_ENTRY_SCHEMA.md) | Typed semantic contracts and validation rules |
| Semantic integrity | [SEMANTIC_INTEGRITY.md](SEMANTIC_INTEGRITY.md) | Finalization, integrity seals, immutable transitions, and correction rules |
| Truth status | [TRUTH_STATUS_POLICY.md](TRUTH_STATUS_POLICY.md) | Truth-state admission and review policy |

## Canonical source specifications

- [Grapher Modernization Master Agent Implementation Order.pdf](Grapher%20Modernization%20Master%20Agent%20Implementation%20Order.pdf) — original modernization implementation specification.
- [Grapher Provenance and Future Training Readiness.pdf](Grapher%20Provenance%20and%20Future%20Training%20Readiness.pdf) — provenance and future-training-readiness addendum.
- [grapher-hardening-instructions.txt](grapher-hardening-instructions.txt) — v0.4.1 hardening instruction set retained for forensic/historical reference.

## Diagram index

- [Architecture overview](ARCHITECTURE.md#architecture-overview)
- [Canonical mutation architecture](ARCHITECTURE.md#canonical-mutation-architecture)
- [Checkpoint and compaction architecture](ARCHITECTURE.md#checkpoint-and-compaction-architecture)
- [Standard change procedure](PROCEDURES.md#standard-change-procedure)
- [Self-graph and CI procedure](PROCEDURES.md#self-graph-and-ci-procedure)
- [Checkpoint refresh procedure](PROCEDURES.md#checkpoint-refresh-procedure)
- [Compaction preview procedure](PROCEDURES.md#compaction-preview-procedure)
- [Codex architecture](CODEX_INTEGRATION.md#architecture-diagram)
- [Codex procedure](CODEX_INTEGRATION.md#procedure-flow)
- [M10 architecture](M10_CURSOR_DASH_EDITING.md#architecture-diagram)
- [M10 Cursor procedure](M10_CURSOR_DASH_EDITING.md#cursor-procedure)
- [Approved Dash edit procedure](M10_CURSOR_DASH_EDITING.md#approved-dash-edit-procedure)

## Indexing policy

Every human-facing `.md`, `.pdf`, and `.txt` file directly under `docs/` must be listed here. CI enforces this with `scripts/check_docs_index.py`. Machine-oriented Grapher packs under `docs/grapher/` are intentionally excluded from the human documentation index.

## Commit anchors

M8 governance/documentation entered `main` at `5bb12e176e6310759288af10354cea4ddd01703f`. M9 Codex-first integration entered `main` at `abcc77ea846d206c31f59e58c5ceb858b96089f1`. M10 branches from that state.
