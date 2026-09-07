# Changelog

## Unreleased

- Added an opt-in explicit truth-status admission policy that rejects newly authored `unclassified` nodes at the canonical mutation save boundary while preserving deliberate ingest/review exceptions.
- Added a CI truth-status gate and a finite legacy review allowlist so existing classification debt cannot silently expand.

## 0.5.0 — 2026-09-05

- Added strict typed semantic contracts for durable reasoning/work records, including exact allowed fields, field-type validation, filler rejection, and machine-readable contract introspection.
- Added Git-backed `grapher publish` / `grapher sync` transport with deterministic snapshots, graph hashes, manifests, immutable publication records, unpublished-change protection, and local vector rebuilds.
- Added compact-context guidance as a canonical agent workflow rule and synchronized generated Codex/Cursor documentation with the new schema and transport behavior.
- Updated human documentation and examples so semantic node commands satisfy the enforced contracts.
- Verified cross-checkout synchronization and recorded the 2026-09-05 maintenance baseline in Grapher's own shared graph.

## 0.4.1 — 2026-09-03

- Hardened finalized-record immutability, audited administrative deletion, mutation actor attribution, and provenance/history behavior.
