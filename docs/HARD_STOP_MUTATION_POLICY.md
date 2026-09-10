# Hard-stop mutation policy

Grapher records are append-oriented. Once a node has become a committed record, supported Grapher mutation paths must not rewrite or delete its assertion-bearing identity.

## Hard-stop invariant

A committed record may not be rewritten in place. Corrections are represented as new records linked through supersession, contradiction, invalidation, or another explicit relation.

The only in-place exception in this release is completion of a pending ingest draft. A pending ingest draft is an unclassified ingest stub whose content is empty or whose ingest metadata still marks it pending. Draft enrichment may add substantive content and operational metadata, but it may not change the record's id, type, path, or creation time.

Truth status remains a materialized compatibility cache backed by immutable `status_transition` records. Lifecycle stage, workflow state, verification state, sealing metadata, and timestamps remain operational fields in this beta and are not yet converted to first-class event records.

## Unsupported operations

The hard-stop release removes supported administrative bypasses for finalized record rewrites and deletion. `--force-finalized` is no longer a CLI option, and `grapher add` no longer silently upserts an existing id or path.

Existing committed nodes cannot be removed through `grapher rm`. Merge operations that would rewrite or delete committed nodes are rejected. Import/merge operations may add new records but may not overwrite local records with colliding ids. Replace-mode imports into a non-empty graph are rejected.

## Correction workflow

1. Create a new correcting record with a new id.
2. Link the correcting record to the original with `supersedes`, `contradicts`, `fixes`, or another precise relation.
3. Use truth-status transitions when the treatment of the original record changes.
4. Preserve the original record and its provenance.

## Scope

This release is a hard stop, not the final immutable-ledger architecture. `knowledge.json` remains the materialized canonical document and `history.jsonl` remains the mutation journal. A later release should make the append-only event ledger authoritative and regenerate `knowledge.json` as a projection.
