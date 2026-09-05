# Study log

## 2026-09-05 — Study initialized against Grapher v0.5.0

### Baseline

Grapher v0.5.0 is the first suitable baseline because semantic records have strict typed contracts and shared Git transport provides immutable snapshot identity.

### Decision

Use a downstream, model-agnostic interchange format (`Grapher Derived Example v1`) rather than adding training-specific fields to Grapher itself.

### First fixture

`examples/grapher-v050-sequence.json` demonstrates that a derived example can preserve graph identity, typed source/target records, relationships, evidence/provenance, quality state, and leakage grouping without recovering the original transcript.

### What this proves

The graph contains enough normalized structure to represent candidate training/evaluation examples.

### What this does not prove

It does not establish automatic extraction reliability, optimal reasoning, sufficient example kinds, or model improvement.

## 2026-09-05 — Exporter prototype + Case Study 001

Implemented read-only exporter `0.1.1` outside `src/grapher/` and ran it against Grapher's own published graph (`fe42beb0...`).

Results after correcting edge direction: 13 semantic candidates; 4 eligible; 9 rejected. The initial symmetric-neighbor extractor leaked later state backward, so exporter `0.1.1` now accepts only directed antecedent relations emitted by the target.

## 2026-09-05 — Case Study 002: pocket-synth legacy corpus

Pinned public `seanbman/pocket-synth` at `33928620f31c70d86da9a4f9133aec897752f3f0` and analyzed its existing `.grapher/knowledge.json` without modifying or copying the source graph into Grapher.

Exporter `0.1.3` found 196 nodes / 386 edges, but only 1 current semantic-type node and 0 canonical semantic objects; strict export therefore produced 0 eligible examples. This identified legacy semantic vocabulary/content—not graph size or connectivity—as the limiting factor.

## 2026-09-05 — Legacy normalization study 001

Added read-only preview `0.1.0` and ran it against the same pinned pocket-synth graph.

Results:

- 196 nodes total;
- 80 `enrichment_required`;
- 116 `context_only`;
- 0 `mechanically_mappable`.

The 80 enrichment records are 78 ambiguous `finding` nodes, 1 legacy `instruction`, and 1 free-text `decision`. The remaining concepts, documents, images, video, and checkpoints have no safe semantic retype and remain context-only.

### Iteration learned

There is no defensible bulk auto-migration for this legacy corpus. Normalization should therefore be an explicit enrichment workflow that presents candidate types/required fields to a human or agent, preserves the original record, and creates a typed successor only when the missing semantics are actually supplied. The exporter quality bar remains unchanged.
