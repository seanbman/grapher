# Grapher Technology Debt Review — 2026-09-06

This review follows completion of the M1–M12 modernization sequence. It is maintenance work and does not create or renumber a milestone. The sweep was merged to `main` at `ad75fee8df1f33cd8890bfbd23924b35cc6f4903`.

## Summary

The repository is in strong functional shape after M11 acceptance and M12 closure. The sweep resolved the safe, high-value maintainability and governance items immediately and recorded larger structural work explicitly instead of hiding it inside unrelated changes.

## Resolved in the sweep

| Area | Debt | Resolution |
|---|---|---|
| Package metadata | `pyproject.toml` still described Grapher as a Cursor/Codex-specific CLI | Reworded as a project-local durable work graph for humans and autonomous agents, matching the shipped architecture |
| Self-graph governance | CI accepted any sufficiently large JSON file under `pass-records/` | Pass records are now parsed and structurally validated for identity, explicit status, semantic/content payload, and actor/source provenance |
| Packaging confidence | CI compiled and tested the editable source tree but did not prove the package/CLI could actually build and start | Added `uv build`, import smoke testing, and `grapher --help` execution on Python 3.10 and 3.12 |
| Research workflow dependency | `jsonschema` was installed without a bounded major version | Bounded the dependency to reduce unexpected CI breakage |
| Debt visibility | No single post-modernization debt ledger existed | This indexed review records resolved and deferred debt with ownership boundaries |

## Structural debt retained deliberately

### CLI monolith

`src/grapher/cli.py` is approximately 60 KB and remains the largest concentration of dispatch, argument parsing, and command orchestration. It is functioning and covered by the existing suite, so splitting it during a broad cleanup would create unnecessary regression risk.

Recommended follow-up: extract command families behind stable handlers (`checkpoint`, `curate`, `migrate`, `integrations`, `dash`, query/read commands) while preserving the current CLI surface and adding parser/dispatch contract tests before each extraction.

### Legacy v1 compatibility

Read-only v1 compatibility and migration remain intentional product behavior. They are not dead code while legacy fixture compatibility is part of M11 acceptance. Removal should happen only through an explicit deprecation policy and migration horizon, not opportunistic cleanup.

### Five grandfathered `unclassified` records

The truth-status allowlist still contains five historical records created before explicit truth-state admission became mandatory. They are a finite curation queue, not a reason to weaken the current gate. They should be curated through Grapher's immutable status-transition path and then removed from the allowlist. Direct JSON status edits are prohibited.

### Optional embedding test isolation

The default suite intentionally excludes the high-memory embedding integration. This is acceptable for ordinary CI, but release automation should continue to run the dedicated embedding test path before releases that modify embedding/search behavior.

## Review procedure

```mermaid
flowchart LR
    BASE["Accepted modernization main\ncommit: 1e3a15b\ncode + tests + docs"]
    SWEEP["Sweep code / CI / metadata / governance\nrepo-wide inspection\nmerged: ad75fee"]
    CLASSIFY["Classify debt\nfix-now vs structural/deferred\nmerged: ad75fee"]
    FIX["Apply safe hardening\npyproject + CI + governance scripts\nmerged: ad75fee"]
    GRAPH["Record maintenance pass\n.grapher/shared/pass-records\nmerged: ad75fee"]
    VERIFY["Full governance + Python matrix\n.github/workflows/ci.yml\naccepted before ad75fee"]

    BASE --> SWEEP --> CLASSIFY --> FIX --> GRAPH --> VERIFY
```

## Architecture impact

```mermaid
flowchart TD
    AUTHORS["Human / Codex / Cursor / other agents"]
    CLI["CLI and integrations\nsrc/grapher/*"]
    STORE["Canonical mutation boundary\nstore.py + integrity/truth policy"]
    SHARED["Versioned shared state\n.grapher/shared/*"]
    CI["Governance + package + tests\n.github/workflows/ci.yml"]

    AUTHORS --> CLI --> STORE --> SHARED
    SHARED --> CI
    CLI --> CI
    CI -->|self-state gate| SHARED
```

## Completion state

The strengthened governance gate, package build/CLI smoke checks, truth-status gate, acceptance suite, research validation, and full Python 3.10/3.12 regression matrix passed before merge at `ad75fee8df1f33cd8890bfbd23924b35cc6f4903`. Structural items above remain explicit follow-up maintenance debt.
