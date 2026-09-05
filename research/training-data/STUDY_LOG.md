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

Results after correcting edge direction:

- 13 semantic candidates;
- 4 eligible (30.77%);
- 9 rejected;
- 3 eligible `decision_to_outcome`, 1 `sequence_completion`;
- 3 eligible targets have verified evidence, 1 declared evidence;
- 8 rejections lacked a directed grounded predecessor;
- 4 involved legacy/non-canonical semantic targets;
- all eligible examples remain in one leakage group.

### Iteration learned from the case study

The initial symmetric-neighbor extractor incorrectly allowed incoming edges to become context, which could leak later implementation/outcome state backward into earlier targets. Exporter `0.1.1` now accepts only directed antecedent relations emitted by the target.

### Next experiment

Run the same exporter unchanged against independent project graphs. Compare eligibility/rejection distributions and inspect whether missing directed antecedent relations represent genuine Grapher modeling gaps or merely sparse project history. Do not change Grapher core until that distinction is supported by multiple case studies.
