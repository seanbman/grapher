# Study log

## 2026-09-05 — Study initialized against Grapher v0.5.0

### Baseline

Grapher v0.5.0 is the first suitable baseline for this study because semantic records now have strict typed contracts and the shared Git transport provides immutable snapshot identity through graph hashes and publication records.

### Decision

Use a downstream, model-agnostic interchange format (`Grapher Derived Example v1`) rather than adding training-specific fields to Grapher itself.

### First fixture

`examples/grapher-v050-sequence.json` manually derives one `sequence_completion` example from the verified v0.5.0 release episode. The fixture demonstrates that a derived example can preserve:

- immutable graph identity;
- source/target semantic records;
- graph relationships;
- evidence/provenance;
- quality-policy state;
- a leakage-safe episode grouping.

### What this proves

The current graph contains enough normalized structure to represent a candidate training/evaluation example without recovering the original conversation transcript.

### What this does not prove

- that the episode is a useful learning objective;
- that automatic episode extraction is reliable;
- that `verified` implies optimal reasoning;
- that the current example kinds are sufficient;
- that a small model will improve from this representation.

### Next experiment

Build a **read-only research exporter prototype** outside `src/grapher/` that consumes `.grapher/shared/knowledge.json` plus its manifest and emits candidate v1 examples without mutating the graph.

For its first pass, measure:

1. candidate count by example kind;
2. rejection count and reason under `research-v1` eligibility;
3. connected episode size;
4. examples lacking enough causal/temporal structure;
5. duplicate or near-duplicate examples;
6. split groups produced from project/mission/generation/episode boundaries.

Then manually review a small sample before considering any training adapter.
