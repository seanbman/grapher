# M11 — Acceptance Fixtures and Tests

M11 turns Grapher's existing representative fixture corpus into an explicit product-level acceptance suite. Each case names the behavior it protects so regressions are evaluated against real usage shapes rather than isolated implementation details.

## Acceptance architecture

```mermaid
flowchart LR
    MANIFEST["Acceptance manifest\ntests/fixtures/acceptance-suite.json\ninception: 0488bc0\ncurrent: M11 branch"]
    GENERIC["Generic museum v1 fixture\ntests/fixtures/museum-exhibit.json\ninception: 0488bc0\ncurrent: M11 branch"]
    MULTI["Multi-agent Dreadnought fixture\ntests/fixtures/dreadnought-control.json\ninception: 0488bc0\ncurrent: M11 branch"]
    LEGACY["Large legacy CASSIO fixture\ntests/fixtures/cassio-brain.json\ninception: 0488bc0\ncurrent: M11 branch"]
    TESTS["Acceptance runner\ntests/test_m11_acceptance_suite.py\ninception: 0488bc0\ncurrent: M11 branch"]
    CI["Python 3.10 + 3.12 and governance\n.github/workflows/ci.yml\ninception: 0488bc0\ncurrent: M11 branch"]

    MANIFEST --> TESTS
    GENERIC --> TESTS
    MULTI --> TESTS
    LEGACY --> TESTS
    TESTS --> CI
```

## Acceptance procedure

```mermaid
flowchart LR
    DECLARE["Declare named case + expected capabilities\nacceptance-suite.json\ninception: 0488bc0\ncurrent: M11 branch"]
    LOAD["Load representative fixture\ntests/fixtures/*\ninception: 0488bc0\ncurrent: M11 branch"]
    EXERCISE["Exercise public Grapher behaviors\nmigration / audit / ranking / context / export\ninception: 0488bc0\ncurrent: M11 branch"]
    ASSERT["Assert product-level invariants\ntest_m11_acceptance_suite.py\ninception: 0488bc0\ncurrent: M11 branch"]
    GATE["Require full CI success before roadmap advance\n.github/workflows/ci.yml\ninception: 0488bc0\ncurrent: M11 branch"]

    DECLARE --> LOAD --> EXERCISE --> ASSERT --> GATE
```

## Cases

`generic-v1-migration` protects non-software compatibility and idempotent migration using the museum fixture. `multi-agent-generation-truth` protects generation scoping, truth-aware ranking, preservation of contaminated historical evidence, generalized agent context, non-canonical Dash export, and audit behavior using the Dreadnought control fixture. `legacy-rich-graph-read` protects inspection compatibility for the large CASSIO legacy corpus without forcing destructive normalization merely to read it.

## Acceptance rule

A fixture is not merely test data. Its manifest entry must state why it exists and which user-visible capabilities it protects. M11 is complete when the declared suite passes on the supported CI matrix and the governance/self-graph gates remain green.
