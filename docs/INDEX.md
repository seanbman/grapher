# Grapher Documentation Index

This is the canonical entry point for Grapher documentation. Human and agent readers should start here, then follow the topic links below.

## Core navigation

| Topic | Document | Purpose |
|---|---|---|
| Architecture | [ARCHITECTURE.md](ARCHITECTURE.md) | System boundaries, canonical state, mutation path, transport, Dash, and agent integrations |
| Procedures | [PROCEDURES.md](PROCEDURES.md) | Change procedure, self-graph publication, CI gates, checkpoints, compaction, and release flow |
| Roadmap | [ROADMAP.md](ROADMAP.md) | Canonical M1-M12 implementation order and completed modernization state |
| v0.6.1 release | [RELEASE_0.6.1.md](RELEASE_0.6.1.md) | Embedded-interface compatibility baseline and upgrade guidance |
| v0.6.0 release | [RELEASE_0.6.0.md](RELEASE_0.6.0.md) | Release baseline, included capabilities, verification, merge, and tag procedure |
| Interactive CLI | [INTERACTIVE_CLI.md](INTERACTIVE_CLI.md) | Arrow-key menu, guided initialization, stdin configuration editing, and automation compatibility |
| Embedded integration | [EMBEDDED_INTEGRATION.md](EMBEDDED_INTEGRATION.md) | Host-agnostic application boundary for embedding Grapher without bypassing canonical mutation rules |
| Embedded brokering | [EMBEDDED_BROKERING.md](EMBEDDED_BROKERING.md) | Practical read-broker/write-mediation contract, provenance, examples, and host integration pattern |
| Codex integration | [CODEX_INTEGRATION.md](CODEX_INTEGRATION.md) | M9 generalized agent contract and Codex-first integration procedure |
| Cursor + Dash editing | [M10_CURSOR_DASH_EDITING.md](M10_CURSOR_DASH_EDITING.md) | M10 shared Cursor contract plus proposal-first, approval-gated Dash editing architecture |
| Acceptance suite | [M11_ACCEPTANCE.md](M11_ACCEPTANCE.md) | M11 named fixture cases and product-level acceptance procedure |
| Modernization completion | [M12_COMPLETION.md](M12_COMPLETION.md) | M12 documentation reconciliation, closure evidence, and full-suite completion state |
| Technology debt review | [TECH_DEBT_REVIEW_2026-09-06.md](TECH_DEBT_REVIEW_2026-09-06.md) | Post-modernization debt sweep, resolved maintenance items, and explicitly deferred structural debt |
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
- [Interactive CLI architecture](INTERACTIVE_CLI.md#architecture-diagram)
- [Interactive CLI procedure](INTERACTIVE_CLI.md#procedure-flow)
- [Embedded integration architecture](EMBEDDED_INTEGRATION.md#architecture-diagram)
- [Embedded integration procedure](EMBEDDED_INTEGRATION.md#procedure-flow)
- [Embedded brokering architecture](EMBEDDED_BROKERING.md#appendix--architecture)
- [Embedded brokering process](EMBEDDED_BROKERING.md#appendix--process-flow)
- [Codex architecture](CODEX_INTEGRATION.md#architecture-diagram)
- [Codex procedure](CODEX_INTEGRATION.md#procedure-flow)
- [M10 architecture](M10_CURSOR_DASH_EDITING.md#architecture-diagram)
- [M10 Cursor procedure](M10_CURSOR_DASH_EDITING.md#cursor-procedure)
- [Approved Dash edit procedure](M10_CURSOR_DASH_EDITING.md#approved-dash-edit-procedure)
- [M11 acceptance architecture](M11_ACCEPTANCE.md#acceptance-architecture)
- [M11 acceptance procedure](M11_ACCEPTANCE.md#acceptance-procedure)
- [M12 completion architecture](M12_COMPLETION.md#completion-architecture)
- [M12 completion procedure](M12_COMPLETION.md#completion-procedure)
- [Technology debt review procedure](TECH_DEBT_REVIEW_2026-09-06.md#review-procedure)
- [Technology debt architecture impact](TECH_DEBT_REVIEW_2026-09-06.md#architecture-impact)
- [v0.6.1 release procedure](RELEASE_0.6.1.md#appendix--process-flow)
- [v0.6.0 release procedure](RELEASE_0.6.0.md#release-procedure)

## Indexing policy

Every human-facing `.md`, `.pdf`, and `.txt` file directly under `docs/` must be listed here. CI enforces this with `scripts/check_docs_index.py`. Machine-oriented Grapher packs under `docs/grapher/` are intentionally excluded from the human documentation index.

## Commit anchors

M8 governance/documentation entered `main` at `5bb12e176e6310759288af10354cea4ddd01703f`. M9 Codex-first integration entered `main` at `abcc77ea846d206c31f59e58c5ceb858b96089f1`. M10 entered `main` at `0488bc0d1d452e4f8643124a67ed5829b0cc4175`. M11 entered `main` at `ffe702381e3b08bdee21987ea13bc2fcde6d6cf2`. The M12 closure framework entered `main` at `1e3a15bad6b38b523eda9023e1ee92dc2947d2`. The post-modernization maintenance sweep and final M12 closure verification entered `main` at `ad75fee8df1f33cd8890bfbd23924b35cc6f4903`. Embedded host integration entered `main` at `b3729dadc318b6eb65c593e47bcd8da272147d4d`. Release 0.6.1 documents and stabilizes that interface as a compatibility baseline.
