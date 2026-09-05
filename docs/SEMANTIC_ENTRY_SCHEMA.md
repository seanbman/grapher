# Typed semantic entries

Grapher treats durable knowledge as structured semantic records rather than free-form notes.

Canonical types and required payload fields:

| Type | Required JSON fields |
|---|---|
| observation | `observation`, `source` |
| problem | `problem`, `impact` |
| question | `question`, `importance` |
| hypothesis | `hypothesis`, `basis`, `validation_condition` |
| requirement | `requirement`, `acceptance_condition` |
| constraint | `constraint`, `reason` |
| proposal | `proposal`, `rationale` |
| decision | `decision`, `rationale` |
| task | `action`, `expected_outcome` |
| implementation | `change`, `component` |
| test | `test`, `method`, `outcome` |
| result | `result`, `evidence` |
| failure | `failure`, `observed_behavior` |
| lesson | `lesson`, `derived_from` |

Use JSON object content:

```bash
grapher add \
  --type decision \
  --title "Typed Grapher entries" \
  --content '{"decision":"Use typed semantic entries","rationale":"Normalize knowledge at write time"}' \
  --status current
```

Rules:

- Non-semantic node types such as `document`, `image`, `audio`, `component`, and `artifact` retain normal free-form `content`.
- Semantic types may exist with empty content as temporary working stubs while unclassified/unverified.
- Once semantic content is written, it must be valid JSON and satisfy the type schema.
- `current`, `canonical_spec`, partially/fully verified, and finalized semantic nodes cannot remain empty.
- Obvious filler such as `TBD`, `TODO`, `unknown`, or `investigate later` does not satisfy required fields.
- `test.outcome` is constrained to `pass`, `fail`, `partial`, or `inconclusive`.
- `lesson.derived_from` must be a non-empty list.
- Parsed payloads are persisted as the node's `semantic` object, giving downstream normalization a stable machine-readable field.

Legacy semantic records remain readable. An unchanged legacy free-form semantic record may still receive operational updates, but rewriting its semantic content requires conversion to the structured form.
