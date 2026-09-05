# Grapher Git transport

Grapher separates local runtime state from Git-shared knowledge.

## Local only

These files change during normal agent work and must not be committed:

- `.grapher/knowledge.json`
- `.grapher/history.jsonl`
- `.grapher/vectors.json`
- `.grapher/sync-state.json`
- migration backups

## Shared through Git

`grapher publish` validates and writes:

- `.grapher/shared/knowledge.json` — deterministic normalized snapshot
- `.grapher/shared/manifest.json` — graph hash, schema, embedding metadata
- `.grapher/shared/history/<publication-id>.json` — immutable publication record

Vectors are never published. They are derived locally from the shared graph.

## Workflow

Before pushing meaningful knowledge:

```bash
grapher publish
git add .grapher/shared
git commit -m "grapher: publish project knowledge"
git push
```

After pulling peer changes:

```bash
git pull
grapher sync
```

`grapher sync` refuses to overwrite unpublished local graph changes. Publish them first or explicitly use `grapher sync --force` when discarding them is intentional.

Use `grapher sync --no-vectors` to hydrate the graph without rebuilding the local embedding cache. If the embedding extra is unavailable, sync still succeeds and reports vectors as pending.

## Concurrency boundary

Publication collapses many local graph mutations into one Git-visible snapshot. Immutable publication records avoid peers appending to one shared history file. Concurrent snapshot reconciliation is a separate concern; this transport layer intentionally does not silently merge divergent published graphs.
