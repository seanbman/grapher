# Training-data research rules

This directory is a downstream research consumer of Grapher, not part of Grapher's canonical runtime model.

- Keep Grapher core model-agnostic. Do not add prompts, tokenization, model architecture, reward labels, or training-specific fields to `src/grapher/` merely to simplify this study.
- Treat `schema.v1.json` as the current canonical interchange contract for experiments.
- Derived examples must be auditable back to an immutable Grapher graph hash and source records.
- Never invent missing rationale, evidence, causal links, or outcomes to complete an example.
- Preserve status, verification, provenance, contradictions, supersession, and scope when deciding eligibility.
- Keep train/evaluation leakage prevention explicit through `split_group`; do not randomly split examples from the same work episode.
- Log experiments, rejection patterns, and schema concerns in `STUDY_LOG.md`.
- Prefer changing extraction/quality policy here before proposing a Grapher core-schema change. Core changes require evidence of a general work-graph deficiency, not a model-specific convenience.
