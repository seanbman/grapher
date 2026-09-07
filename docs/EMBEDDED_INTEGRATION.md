# Embedded Integration

Grapher can be embedded inside a larger control system without surrendering ownership of its durable graph semantics.

Host applications should import `grapher.integrations.embedded` rather than reading or writing `.grapher/knowledge.json` or `history.jsonl` directly. The embedded surface delegates mutations to Grapher's canonical store boundary, preserving truth policy, semantic integrity, status transitions, provenance history, and rollback behavior.

The host remains responsible for authorization and admission policy. Grapher remains responsible for representation and durable mutation correctness. This keeps Grapher independently usable from its CLI while allowing an encapsulating system to act as the only writer in its own runtime.

## Supported boundary

The host-agnostic module currently exposes initialization, query, contribution, relationship, neighborhood, ingestion, inference, reindex, feedback, and delta operations through the same implementation already exercised by Grapher integrations.

A host should pass explicit `source`, `actor`, `scope`, `provenance`, `operation_id`, and `phase` information where available. Host-specific schemas should be projected into Grapher-compatible types and metadata before calling this boundary; hosts must not bypass Grapher validation by editing local state files directly.

## Architecture diagram

```mermaid
flowchart LR
    H[Host control system] -->|authorized read/write request| E[grapher.integrations.embedded]
    E --> G[Graph operations]
    G --> S[save_graph_mutation]
    S --> K[(Local canonical graph)]
    S --> P[(Structured history)]
    K --> V[validate / audit]
    V --> T[publish / sync transport]
    T --> SH[(.grapher/shared)]
```

## Procedure flow

```mermaid
flowchart TD
    A[Host validates its own authority and schema] --> B[Project into Grapher representation]
    B --> C[Call embedded integration API]
    C --> D[Grapher mutates through canonical store]
    D --> E[Truth, semantic, integrity and transition checks]
    E --> F[Atomic graph + structured history]
    F --> G[Validate and audit]
    G --> H[Publish when shared Git state is required]
```

The legacy `grapher.integrations.agent_hub` module remains available for compatibility. New host systems should prefer `grapher.integrations.embedded`.
