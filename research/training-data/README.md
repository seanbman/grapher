# Grapher evaluation/training data study

This directory is a living research area for testing whether Grapher can reliably produce useful evaluation and model-training data.

It is deliberately **downstream of Grapher**. Grapher remains a model-agnostic work/provenance graph. No model-specific prompts, quality labels, fine-tuning logic, or training-runtime concerns belong in Grapher's canonical node schema.

## Current canonical research contract

`schema.v1.json` defines **Grapher Derived Example v1**, an intermediate interchange format between a Grapher snapshot and later model-specific datasets.

The intended pipeline is:

```text
Grapher graph
  -> eligibility/episode extraction
  -> Grapher Derived Example v1
  -> train/eval split
  -> model-specific adapter
  -> SFT / evaluation / preference / other dataset
```

This keeps the source record stable while allowing downstream adapters to change.

## What one derived example contains

A v1 example preserves:

- the exact source graph hash and snapshot reference;
- project/mission/generation scope when present;
- an ordered set of input records and relationships;
- one or more target records and relationships;
- normalized semantic or text content;
- provenance/evidence signals needed to judge eligibility;
- an explicit quality-policy version and warnings;
- a `split_group` used to prevent train/evaluation leakage;
- exporter identity/version.

It does **not** contain a chat prompt or model-specific tokenization.

## Initial example kinds

- `state_to_decision` — prior state/constraints -> recorded decision.
- `state_to_action` — prior state/decision -> recorded task or implementation.
- `decision_to_outcome` — decision/implementation -> observed result.
- `failure_to_lesson` — evidenced failure -> derived lesson.
- `verification_judgment` — claim/test/evidence -> recorded verification outcome.
- `sequence_completion` — partial grounded episode -> next recorded semantic state.

These are hypotheses for study, not claims that each kind will ultimately be useful.

## Default eligibility policy: `research-v1`

An exporter should default to conservative inclusion:

1. Every referenced source node and relationship must exist in the same immutable snapshot.
2. Semantic records must satisfy Grapher's semantic contract.
3. Empty/pending ingest stubs are excluded.
4. A target marked `superseded`, `rejected`, or `deprecated` is excluded unless the example is explicitly historical/contrastive.
5. Unresolved contradictions produce a warning and are excluded by default from positive targets.
6. Result/test/failure targets require attributable evidence or an explicit verified relation.
7. Decisions are not treated as "good" merely because they were made; stronger examples should connect decisions to later evidenced outcomes.
8. Agent-authored material is not treated as independently verified solely because an agent wrote it.
9. Export must preserve enough source provenance to audit every derived example back to Grapher.
10. No exporter may invent missing rationale, evidence, outcomes, or relationships to make an episode look complete.

Eligibility is a selection policy, not a truth oracle.

## Leakage policy

Random per-example splitting is unsafe because multiple examples can come from the same work episode.

`split_group` should therefore be stable at the strongest available boundary, normally:

```text
project_id / mission_id / generation_id / episode_id
```

When those fields are absent, the exporter must derive a deterministic connected-component/episode grouping and record how it was obtained. All examples from one split group stay in the same train/validation/test partition.

## Study cadence

This is an ongoing study alongside normal Grapher development. At meaningful Grapher releases or schema changes we should:

1. export a sample from Grapher's own graph and at least one real external project graph;
2. count eligible/rejected examples by example kind and rejection reason;
3. manually inspect a small stratified sample;
4. log failure modes in `STUDY_LOG.md`;
5. adjust extraction/quality policy before changing Grapher's core schema;
6. only change Grapher itself when the study reveals a general work-graph deficiency, not merely a model-training convenience.

## Current research questions

- Can explicit semantic relationships reconstruct coherent reasoning/work episodes without transcript recovery?
- Which relation patterns reliably distinguish correlation from causal sequence?
- What evidence threshold produces useful targets without discarding too much data?
- How should superseded and failed paths be used as negative/contrastive examples without teaching obsolete state as canonical truth?
- Which example kinds are most valuable for very small local models?
- How much human review is needed before derived examples become suitable for training?
- What normalization is required for legacy pre-semantic Grapher records?
- Which grouping strategy best prevents leakage across related project episodes?

## Non-goals

This research area does not train models, choose a model architecture, score agents as good/bad, or add ML-specific fields to Grapher's graph. Those remain downstream concerns.
