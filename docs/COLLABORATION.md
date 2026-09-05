# Multi-agent collaboration

Grapher treats Git as transport, not as the semantic merge engine.

## Local workflow

Create one isolated arm per agent:

```bash
grapher arm --actor agent-a
grapher arm --actor agent-b
```

Run each agent against the returned arm graph, for example with `GRAPHER_GRAPH`.
Each arm starts from the same shared snapshot and has its own local `knowledge.json`.

When an arm reaches a useful checkpoint:

```bash
grapher changeset --actor agent-a --graph .grapher/arms/agent-a/knowledge.json
grapher changeset --actor agent-b --graph .grapher/arms/agent-b/knowledge.json
```

Changesets are immutable files under `.grapher/shared/changes/<actor>/` and are safe to carry through Git.

Reconcile them into the canonical local graph:

```bash
grapher reconcile
```

Independent node changes and disjoint fields merge automatically. Competing values for the same field, delete-vs-update operations, incompatible edge changes, and stale-base changesets produce a conflict report under `.grapher/conflicts/`. Reconciliation is atomic: any conflict prevents a partial canonical write.

After a clean reconciliation:

```bash
grapher publish
```

The publication manifest records the included changeset ids so peers do not replay them after pulling the shared snapshot.

## Distributed workflow

The same files move through Git:

```text
shared snapshot -> agent arms -> immutable changesets -> Git -> reconcile -> publish
```

Vectors, arm graphs, conflict reports, and reconciliation state remain local and ignored by Git.
