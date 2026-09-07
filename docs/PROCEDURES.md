# Grapher Procedures

[Documentation index](INDEX.md) · [Architecture](ARCHITECTURE.md) · [Roadmap](ROADMAP.md)

These procedures define the required operating flow for substantive Grapher changes. The diagrams are executable policy descriptions: code, documentation, tests, and Grapher's own `.grapher` state advance together.

## Standard change procedure

```mermaid
flowchart TD
    START["Start from canonical roadmap + current main\ndocs/ROADMAP.md\ninception: 9917cc8\ncurrent: 453b543"]
    READ["Inspect current graph + relevant code\n.grapher/shared + src/grapher/*\ninception: 9917cc8\ncurrent: 453b543"]
    BRANCH["Create scoped branch\nGit workflow\ninception: 9917cc8\ncurrent: 453b543"]
    CHANGE["Implement bounded change\nsrc/grapher/*\ninception: 9917cc8\ncurrent: 453b543"]
    TEST["Add/update regression tests\ntests/*\ninception: 9917cc8\ncurrent: 453b543"]
    DOC["Update indexed docs + diagrams\ndocs/INDEX.md\ninception: 9917cc8\ncurrent: 453b543"]
    GRAPH["Record pass in Grapher self-state\n.grapher/shared/*\ninception: 9917cc8\ncurrent: 453b543"]
    CI["Run CI gates\n.github/workflows/ci.yml\ninception: 9917cc8\ncurrent: 453b543"]
    PR["Review PR; merge only when green\nGitHub PR\ninception: 9917cc8\ncurrent: 453b543"]

    START --> READ --> BRANCH --> CHANGE --> TEST --> DOC --> GRAPH --> CI --> PR
```

A code-only pass is incomplete. Documentation-only changes that alter architecture, policy, procedures, roadmap, or agent behavior are also substantive and must carry a self-state record.

## Self-graph and CI procedure

```mermaid
flowchart TD
    DIFF["Determine changed files\nscripts/check_self_graph_update.py\ninception: 9917cc8\ncurrent: 453b543"]
    SUB{"Substantive Grapher change?"}
    SKIP["No self-graph requirement\nnon-substantive diff"]
    SHARED{".grapher/shared changed?"}
    FAIL1["FAIL CI\nmissing self-state update"]
    MODE{"Pass record or full publication?"}
    RECORD["Versioned pass record\n.grapher/shared/pass-records/*.json"]
    PUB["Canonical publication\nknowledge.json + manifest.json + history/*.json"]
    DOCS["Check docs index + diagrams\nscripts/check_docs_index.py"]
    TESTS["Compile + tests + truth-status gate"]
    PASS["CI green"]

    DIFF --> SUB
    SUB -- no --> SKIP --> DOCS
    SUB -- yes --> SHARED
    SHARED -- no --> FAIL1
    SHARED -- yes --> MODE
    MODE -- pass record --> RECORD --> DOCS
    MODE -- full publish --> PUB --> DOCS
    DOCS --> TESTS --> PASS
```

A pass record is lightweight evidence that the pass was represented inside versioned `.grapher/shared` state. A canonical publication remains the stronger form and is required whenever the canonical graph itself changes. Pass records must not be used as a substitute for publishing semantic graph mutations.

## Checkpoint refresh procedure

```mermaid
flowchart TD
    CREATE["Create checkpoint\nsrc/grapher/checkpoint.py\ninception: 9917cc8\ncurrent: 453b543"]
    SNAP["Capture source state + hashes\n.grapher/checkpoints/*.json\ninception: 9917cc8\ncurrent: 453b543"]
    CHANGE["Source graph evolves\nsave_graph_mutation\ninception: 9917cc8\ncurrent: 453b543"]
    PREVIEW["checkpoint refresh --dry-run\ncompare semantic hashes\ninception: 9917cc8\ncurrent: 453b543"]
    SAFE{"Missing refs or contradictions?"}
    CURATE["Curate/resolve first\nsrc/grapher/curate.py"]
    APPLY["checkpoint refresh --yes\nreviewed mutation"]
    NEW["Write refreshed durable snapshot"]

    CREATE --> SNAP --> CHANGE --> PREVIEW --> SAFE
    SAFE -- yes --> CURATE --> PREVIEW
    SAFE -- no --> APPLY --> NEW
```

Checkpoint refresh is review-first. Timestamp changes alone are insufficient evidence; semantic snapshot hashes are used to detect actual source drift.

## Compaction preview procedure

```mermaid
flowchart TD
    TOPIC["Select topic\ngrapher curate compact --topic ... --dry-run\ninception: 9917cc8\ncurrent: 453b543"]
    CAND["Collect candidate nodes\nsrc/grapher/curate.py\ninception: 9917cc8\ncurrent: 453b543"]
    SCOPE{"Single compatible project / mission / generation?"}
    BLOCK["Return blocked review result\nno cross-scope compaction"]
    RISKS["Report contradictions, provenance concerns, low-information relations"]
    REVIEW["Human/agent review"]
    CURATE["Use explicit checkpoint/status/relation/supersession operations"]
    PRESERVE["Original records remain preserved"]

    TOPIC --> CAND --> SCOPE
    SCOPE -- no --> BLOCK
    SCOPE -- yes --> RISKS --> REVIEW --> CURATE --> PRESERVE
```

Compaction never silently deletes disagreement, rewrites provenance, or crosses mission-generation boundaries. It proposes consolidation; explicit curation performs any accepted change.

## Pull-request acceptance checklist

1. Roadmap consulted and milestone/maintenance classification is correct.
2. Code and tests advance together.
3. Human-facing documentation remains indexed.
4. Architecture/procedure diagrams are updated when affected.
5. Grapher's own `.grapher/shared` state records the pass.
6. `validate`, `audit`, test suite, truth-status gate, documentation gate, and self-graph gate pass.
7. Merge occurs only after the branch head associated with the green CI run is verified.

## Appendix: traceability

Procedure baseline: `9917cc8af31553841294d69000ac33cc2c53daa6`. M8 implementation state before procedure/documentation hardening: `453b543a64851b0c63797c049c04bcc5f848bf8d`.
