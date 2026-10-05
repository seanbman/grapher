# Grapher Git transport

Grapher separates local runtime state from Git-shared knowledge.

## Repository boundary

Grapher deliberately separates its **local brain/runtime** from the small surface that belongs in Git.

Git-safe Grapher paths are limited to:

- `.grapher/config.json` — project Grapher configuration, when intentionally shared;
- `.grapher/shared/**` — explicit publications produced by `grapher publish`.

Everything else under `.grapher/` is local runtime state and must not be committed.

## Local only

These files change during normal agent work and must not be committed:

- `.grapher/knowledge.json`
- `.grapher/history.jsonl`
- `.grapher/vectors.json`
- `.grapher/sync-state.json`
- `.grapher/GRAPHER_CONTEXT.md`
- migration backups, temporary files, caches, and future runtime state

Do **not** use `git add .grapher` and do not use `git add -f` to bypass this boundary.

## Automatic guardrails

`grapher init` now:

1. installs a selective managed block in the repository `.gitignore`;
2. removes an exact broad `.grapher/` ignore rule because it would also hide the legitimate `.grapher/shared/**` publication surface;
3. installs a Grapher-managed local pre-commit hook when no existing pre-commit hook would be overwritten.

If a repository already has its own pre-commit hook, Grapher preserves it rather than replacing user tooling. The command-level guard remains available regardless:

```bash
grapher repo-guard
```

`grapher repo-guard` exits non-zero if any local Grapher runtime path is tracked. `grapher audit` reports the same condition as a critical repository-health issue, and `grapher publish` refuses to publish while forbidden runtime state is tracked.

Existing projects gain the managed ignore policy automatically the next time `grapher publish` runs.

## Shared through Git

`grapher publish` validates and writes:

- `.grapher/shared/knowledge.json` — deterministic normalized snapshot
- `.grapher/shared/manifest.json` — graph hash, schema, embedding metadata
- `.grapher/shared/history/<publication-id>.json` — immutable publication record

Vectors are never published. They are derived locally from the shared graph.

## Workflow

Before pushing meaningful knowledge:

```bash
grapher validate
grapher audit
grapher repo-guard
grapher publish
git add .grapher/config.json .grapher/shared/
grapher repo-guard
git commit -m "grapher: publish project knowledge"
git push
```

If `.grapher/config.json` was not intentionally changed, it does not need to be staged. Never stage the whole `.grapher/` directory.

After pulling peer changes:

```bash
git pull
grapher sync
```

`grapher sync` refuses to overwrite unpublished local graph changes. Publish them first or explicitly use `grapher sync --force` when discarding them is intentional.

Use `grapher sync --no-vectors` to hydrate the graph without rebuilding the local embedding cache. If the embedding extra is unavailable, sync still succeeds and reports vectors as pending.

## Concurrency boundary

Publication collapses many local graph mutations into one Git-visible snapshot. Immutable publication records avoid peers appending to one shared history file. Concurrent snapshot reconciliation is a separate concern; this transport layer intentionally does not silently merge divergent published graphs.
