# Study log

## 2026-09-05 — Study initialized against Grapher v0.5.0

Grapher v0.5.0 became the first baseline suitable for downstream training-data research because semantic records have strict typed contracts and shared Git transport provides immutable snapshot identity. The study uses a model-agnostic derived-example format rather than adding training-specific fields to Grapher.

## 2026-09-05 — Exporter prototype + Case Study 001

Read-only exporter `0.1.1` against Grapher's own published graph produced 13 semantic candidates, 4 eligible and 9 rejected. The case study caught backward leakage from symmetric neighbor extraction, so only directed antecedent relations emitted by the target are now accepted as context.

## 2026-09-05 — Case Study 002: pocket-synth legacy corpus

Pinned `seanbman/pocket-synth@33928620f31c70d86da9a4f9133aec897752f3f0`. Its legacy graph contains 196 nodes / 386 edges, but only 1 current semantic-type node and 0 canonical semantic objects. Strict export correctly produced 0 eligible examples, identifying legacy semantic vocabulary/content as the limiting factor.

## 2026-09-05 — Legacy normalization study 001

Read-only normalization preview `0.1.0` classified the same 196-node graph as:

- 80 `enrichment_required`;
- 116 `context_only`;
- 0 `mechanically_mappable`.

This ruled out defensible bulk auto-migration.

## 2026-09-05 — Enrichment study 001

Added review-first enrichment workflow `0.1.0`. Preview exposes candidate semantic types and exact contracts while leaving candidate values empty. `compose` requires explicit semantic values, actor attribution and a review reason, then delegates validation to Grapher's canonical semantic validator. It emits a proposed typed successor plus `derived_from` lineage without mutating the source graph.

A deterministic three-record pocket-synth slice produced:

- 2 validator-approved successors: one `observation`, one `decision`;
- 1 deferred legacy `instruction`;
- 0 source mutations.

The instruction was deliberately deferred because its prose did not supply the `acceptance_condition` needed for a requirement or the `reason` needed for a constraint. This is the desired failure mode: incomplete legacy meaning remains incomplete rather than being manufactured for normalization.

### Next experiment

Promote the two validated successor bundles into a **disposable copy** of the pinned legacy graph, preserve original records and lineage, then rerun normalization/export metrics. Do not alter the original pocket-synth graph until promotion semantics are proven safe.
