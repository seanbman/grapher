# Changelog

## Unreleased

- Fixed the managed Linux installer so normal release and `--local` installs include both the embedding and Dash visualization runtimes; `grapher dash` no longer requires a separate follow-up extra installation.
- Added installer verification for `dash` and `plotly` alongside `fastembed` and `numpy`, so an incomplete managed runtime fails during installation instead of later at command execution.

## 0.6.1 — 2026-09-07

- Added the host-agnostic `grapher.integrations.embedded` boundary for applications that embed Grapher as a durable knowledge substrate.
- Preserved Grapher's standalone CLI/application behavior while allowing external control systems to own admission and authorization policy.
- Kept all embedded mutations on Grapher's canonical `save_graph_mutation()` path, including truth policy, integrity sealing, immutable transitions, structured history, and rollback.
- Added lossless host metadata fields (`meta`, `stage`, `source_refs`, `owners`) to the embedded contribution surface.
- Added host-side brokering documentation covering read brokering, write mediation, provenance, scope, and publication.

## 0.6.0 — 2026-09-06

- Completed the canonical M1–M12 modernization sequence and formalized the roadmap closure state; there is no implicit M13.
- Added durable checkpoint snapshots with semantic drift detection and generation-safe, review-first compaction previews.
- Added the generalized agent contract (`READ → SEARCH → ACT → RECORD → VALIDATE → PUBLISH`), proven with Codex first and reused by Cursor.
- Added approval-gated Dash status editing with stable proposal IDs, stale-state protection, actor attribution, immutable status transitions, and canonical mutation journaling.
- Added named product-level acceptance fixtures covering generic migration, Dreadnought multi-agent truth/generation behavior, generalized agent context, Dash export, audit behavior, and legacy CASSIO graph compatibility.
- Added CI governance requiring Grapher self-state updates, indexed documentation, architecture/procedure diagrams, explicit truth statuses, package builds, and installed CLI smoke tests on Python 3.10 and 3.12.
- Hardened explicit truth-status admission, finalized-record integrity, actor/provenance attribution, and the Grapher self-graph pass-record gate.
- Added indexed architecture, procedures, Codex/Cursor integration, M11 acceptance, M12 completion, and post-modernization technology-debt documentation.
- Completed the post-modernization debt sweep; retained CLI modularization, intentional v1 compatibility, five legacy `unclassified` records, and dedicated high-memory embedding verification as explicit follow-up maintenance debt.

## 0.5.0 — 2026-09-05

- Added strict typed semantic contracts for durable reasoning/work records, including exact allowed fields, field-type validation, filler rejection, and machine-readable contract introspection.
- Added Git-backed `grapher publish` / `grapher sync` transport with deterministic snapshots, graph hashes, manifests, immutable publication records, unpublished-change protection, and local vector rebuilds.
- Added compact-context guidance as a canonical agent workflow rule and synchronized generated Codex/Cursor documentation with the new schema and transport behavior.
- Updated human documentation and examples so semantic node commands satisfy the enforced contracts.
- Verified cross-checkout synchronization and recorded the 2026-09-05 maintenance baseline in Grapher's own shared graph.

## 0.4.1 — 2026-09-03

- Hardened finalized-record immutability, audited administrative deletion, mutation actor attribution, and provenance/history behavior.
