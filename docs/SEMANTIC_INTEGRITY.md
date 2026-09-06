# Semantic integrity and immutable status transitions

Grapher treats a durable node as an assertion whose meaning must remain inspectable even when the graph later changes how that assertion is classified.

## Core invariant

**Facts are not rewritten to explain a change in interpretation. The change in interpretation is a new fact.**

A node's existing typed semantic content remains the place where its thesis lives. Grapher does not add a second `descriptor` or `thesis` field. For example, a `decision` continues to express its meaning through `decision` and `rationale`; an `implementation` through `change` and `component`.

## Semantic hash

When a node crosses a durable semantic boundary, Grapher attaches an `integrity` record using the `grapher-semantic-v1` SHA-256 scheme.

The hash protects the assertion-bearing record fields:

- node type
- title
- content (structured JSON is canonicalized before hashing)
- tags
- evidence
- source references
- scope
- provenance
- creation time

The local node ID is deliberately excluded so a Grapher pack can prefix IDs during transplantation without invalidating the assertion. Mutable interpretation/operations fields are also excluded: `status`, `workflow_state`, `verification`, lifecycle stage, update/finalization timestamps, and other operational metadata.

A finalized node with an existing invalid semantic seal is rejected rather than silently re-sealed. Pre-integrity finalized nodes may receive their first seal when they are next written through the canonical mutation boundary; this is a compatibility bootstrap, not truth inference.

## Status changes are graph records

`status` remains present as a synchronized compatibility cache for existing search, ranking, CLI, and Dash behavior. It is not the authoritative explanation of how classification changed.

Whenever an existing node's status changes through the canonical save boundary, Grapher creates a finalized `status_transition` child and links it:

```text
subject --status_changed_by--> status_transition
```

The transition content contains:

- `subject_hash`: semantic SHA-256 of the subject assertion
- `from_status`
- `to_status`
- `reason`
- `operation_id`

The child is itself semantically hashed and finalized. Actor provenance is copied from the mutation context. The subject becomes sealed/finalized when it first crosses this boundary, so later status curation may change classification without changing the underlying assertion.

The graph edge identifies the local subject; the transition stores the portable subject hash rather than duplicating a local `subject_id` inside hashed content.

## Rationale precedence

Transition rationale is chosen in this order:

1. explicit mutation `--reason` / API reason;
2. inference explanations already recorded on the subject;
3. a supersession edge and its note;
4. a minimal generated `from -> to` operation description.

Callers should supply an explicit reason whenever a human or agent is adjudicating truth.

## Supersession

Supersession keeps the existing replacement relation:

```text
replacement --supersedes--> original
original    --status_changed_by--> transition(to_status = superseded)
```

The replacement edge answers *what replaced this?* The immutable transition answers *when, by whom, and why did our treatment of the original change?*

## Transferability

Semantic hashes do not depend on local node IDs. A pack may therefore prefix node and edge IDs on import while preserving the semantic identity of the assertions and transition records.

The portable design record for this feature is stored at:

`docs/grapher/semantic-integrity-status-transitions.grapherpack.json`
