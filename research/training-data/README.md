# Grapher evaluation/training data study

This directory is a living research area for testing whether Grapher can reliably produce useful evaluation and model-training data.

It is deliberately **downstream of Grapher**. Grapher remains a model-agnostic work/provenance graph. No model-specific prompts, quality labels, fine-tuning logic, or training-runtime concerns belong in Grapher's canonical node schema.

## Current research pipeline

```text
Grapher graph
  -> legacy normalization preview when needed
  -> explicit semantic enrichment review
  -> validated typed successor bundle
  -> eligibility/episode extraction
  -> Grapher Derived Example v1
  -> train/eval split
  -> model-specific adapter
```

`schema.v1.json` defines **Grapher Derived Example v1**, the model-agnostic interchange format used after normalization.

## Legacy enrichment workflow

`legacy_normalization.py` classifies legacy records as `mechanically_mappable`, `enrichment_required`, or `context_only` without changing the graph.

`enrichment.py preview` then exposes candidate semantic types and their exact required fields. Candidate values are intentionally empty.

`enrichment.py compose` accepts a successor only when the reviewer explicitly supplies:

- one allowed semantic type;
- every required semantic field;
- actor id/kind;
- a review reason.

Grapher's canonical semantic validator then validates the supplied payload. The output is a **proposed successor bundle** plus a `derived_from` relation to the preserved legacy record. The source graph is never mutated by the research workflow.

If required meaning is absent, the record remains deferred. Missing rationale, evidence, acceptance conditions, causes, or relationships must not be invented merely to normalize the corpus.

## Default eligibility policy: `research-v1`

Export is conservative: canonical semantic contracts, evidence/provenance, truth state, directed antecedent relations, contradiction state, and leakage grouping are preserved. Result/test/failure targets require evidence or verified grounding. Superseded/rejected/deprecated targets are excluded by default. Agent-authored content is not independently verified solely because an agent wrote it.

## Leakage policy

Examples from the same work episode remain in one stable `split_group`; random per-example train/eval splitting is not allowed.

## Study cadence

At meaningful Grapher releases or schema changes:

1. test Grapher's own graph and at least one real external project graph;
2. measure eligible/rejected examples and normalization pressure;
3. manually inspect a small stratified sample;
4. log failure modes and enrichment decisions in `STUDY_LOG.md`;
5. change Grapher core only for general work-graph deficiencies, not training convenience.

## Current research questions

- Can explicit semantic relationships reconstruct coherent work episodes without transcript recovery?
- Which evidence threshold produces useful targets without discarding too much data?
- How should failed/superseded paths become contrastive examples safely?
- How much human/agent review is required for legacy enrichment?
- Can validated successor bundles be promoted into a disposable copy of a legacy graph without corrupting lineage or truth state?
- Which grouping strategy best prevents train/evaluation leakage?

## Non-goals

This research area does not train models, choose a model architecture, score agents as good/bad, silently rewrite legacy records, or add ML-specific fields to Grapher's graph.
