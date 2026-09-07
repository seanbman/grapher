# Truth-status admission policy

Grapher separates truth status from workflow state and verification. `unclassified` is a review state, not a safe default for authored knowledge.

## Policy

Projects can enable strict admission in `.grapher/config.json`:

```json
{
  "require_explicit_status": true
}
```

When enabled, canonical mutation saves reject newly created authored nodes whose truth status is still `unclassified`. The rule is enforced at the mutation save boundary so CLI, Agent Hub, and other normal mutation routes share the same behavior.

Allowed exceptions are deliberately narrow:

- raw ingest stubs whose metadata identifies them as pending ingest;
- nodes explicitly marked with `meta.truth_review=true` because a human or agent intentionally placed them in the truth-review queue;
- finite legacy ids listed in `truth_status_legacy_allowlist` while an existing graph is being curated.

The legacy allowlist is migration debt, not a general bypass. New ids should not be added simply to satisfy CI.

## CI

`scripts/check_truth_status.py` scans a strict graph and fails when an authored `unclassified` node exists outside the explicit exceptions. Grapher's own CI runs this check against `.grapher/shared/knowledge.json`.

## Curation guidance

Do not guess status from broad keywords. If evidence is insufficient, mark the node for truth review rather than automatically promoting it. When evidence is sufficient, use Grapher's status curation path so the immutable status-transition machinery records the change.
