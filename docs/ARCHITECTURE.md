# Grapher Architecture

[Documentation index](INDEX.md) · [Procedures](PROCEDURES.md) · [Roadmap](ROADMAP.md)

This document describes Grapher's current architecture as of the M8 hardening pass. Diagram nodes include the relevant code path plus inception/current commit anchors for traceability.

## Architecture overview

```mermaid
flowchart LR
    CLI["CLI\nsrc/grapher/cli.py\ninception: 9917cc8\ncurrent: 453b543"]
    STORE["Canonical store\nsrc/grapher/store.py\ninception: 9917cc8\ncurrent: 453b543"]
    MODEL["Graph/model/semantic contracts\nsrc/grapher/model.py + graph.py + semantic.py\ninception: 9917cc8\ncurrent: 453b543"]
    HISTORY["Immutable mutation history\nsrc/grapher/history.py + integrity.py\ninception: 9917cc8\ncurrent: 453b543"]
    QUERY["Search/audit/retrieval\nsrc/grapher/search.py + audit.py\ninception: 9917cc8\ncurrent: 453b543"]
    CK["Checkpoints\nsrc/grapher/checkpoint.py\ninception: 9917cc8\ncurrent: 453b543"]
    CURATE["Curation/compaction\nsrc/grapher/curate.py\ninception: 9917cc8\ncurrent: 453b543"]
    TRANSPORT["Git transport\nsrc/grapher/transport.py\ninception: 9917cc8\ncurrent: 453b543"]
    DASH["Dash visualization\nsrc/grapher/viz/*\ninception: 9917cc8\ncurrent: 453b543"]
    CODEX["Codex integration\nsrc/grapher/codex_cmd.py + codex_ctx.py\ninception: 9917cc8\ncurrent: 453b543"]
    CURSOR["Cursor integration\nsrc/grapher/cursor_cmd.py\ninception: 9917cc8\ncurrent: 453b543"]

    CLI --> STORE
    STORE --> MODEL
    STORE --> HISTORY
    STORE --> QUERY
    CLI --> CK
    CLI --> CURATE
    CK --> STORE
    CURATE --> STORE
    STORE --> TRANSPORT
    QUERY --> DASH
    CODEX --> CLI
    CURSOR --> CLI
```

The canonical architectural rule is that all semantic mutations converge on the store boundary. Agent integrations, CLI commands, checkpoint refreshes, and curation must not maintain parallel truth systems.

## Canonical mutation architecture

```mermaid
flowchart TD
    INTENT["Human/agent intent\nCLI or integration\ninception: 9917cc8\ncurrent: 453b543"]
    LOAD["load_graph\nsrc/grapher/store.py\ninception: 9917cc8\ncurrent: 453b543"]
    MUTATE["Domain mutation\ngraph / curate / checkpoint\ninception: 9917cc8\ncurrent: 453b543"]
    POLICY["Truth + semantic + integrity policy\ntruth_policy.py + semantic.py + integrity.py\ninception: 9917cc8\ncurrent: 453b543"]
    SAVE["save_graph_mutation\nsrc/grapher/store.py\ninception: 9917cc8\ncurrent: 453b543"]
    GRAPH[".grapher/knowledge.json\nlocal canonical state\ninception: 9917cc8\ncurrent: 453b543"]
    JOURNAL[".grapher/history.jsonl\nappend-only transitions\ninception: 9917cc8\ncurrent: 453b543"]
    PUBLISH["grapher publish\nsrc/grapher/transport.py\ninception: 9917cc8\ncurrent: 453b543"]
    SHARED[".grapher/shared/*\nGit-safe published state\ninception: 9917cc8\ncurrent: 453b543"]

    INTENT --> LOAD --> MUTATE --> POLICY --> SAVE
    SAVE --> GRAPH
    SAVE --> JOURNAL
    GRAPH --> PUBLISH --> SHARED
```

## Checkpoint and compaction architecture

```mermaid
flowchart LR
    SOURCES["Source nodes\ncanonical graph\ninception: 9917cc8\ncurrent: 453b543"]
    CKSVC["Checkpoint service\nsrc/grapher/checkpoint.py\ninception: 9917cc8\ncurrent: 453b543"]
    SNAP["Durable checkpoint snapshot\n.grapher/checkpoints/*.json\ninception: 9917cc8\ncurrent: 453b543"]
    REFRESH["Review-first refresh preview\nsemantic hashes + missing refs + contradictions\ninception: 9917cc8\ncurrent: 453b543"]
    COMPACT["Compaction preview\nsrc/grapher/curate.py\ninception: 9917cc8\ncurrent: 453b543"]
    BOUNDARY["Scope boundary guard\nproject / mission / generation\ninception: 9917cc8\ncurrent: 453b543"]
    REVIEW["Human/agent review\nno destructive auto-merge\ninception: 9917cc8\ncurrent: 453b543"]

    SOURCES --> CKSVC --> SNAP --> REFRESH --> REVIEW
    SOURCES --> COMPACT --> BOUNDARY --> REVIEW
```

M8 strengthens two invariants: checkpoint snapshots preserve enough source state to detect semantic drift, and compaction previews may not aggregate across incompatible project/mission/generation scopes.

## Integration priority

Codex is the first-class integration target in M9. Cursor follows after the agent-agnostic contracts are proven. Neither integration owns canonical truth; both use the same CLI/store boundaries.

## Appendix: traceability

The base architecture for this documentation pass is commit `9917cc8af31553841294d69000ac33cc2c53daa6`. M8 checkpoint/compaction implementation before this documentation pass is commit `453b543a64851b0c63797c049c04bcc5f848bf8d`. Future architecture changes must update both this document and the corresponding Grapher self-state record.
